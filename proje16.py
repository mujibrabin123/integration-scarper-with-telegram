import requests
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters , ConversationHandler, CallbackContext

# Scopus API key (replace with your API key)
SCOPUS_API_KEY = "922723b3f2153e53c8932c72347ce48a"

# Define states for conversation handling
SEARCH_BY_NAME, SEARCH_BY_ID, SEARCH_BY_NAME_ID, SEARCH_BY_DOCUMENT = range(4)  # Define SEARCH_BY_DOCUMENT here

# Define a function to extract author information from Scopus by ID
def extract_author_info(author_id):
    url = f"https://api.elsevier.com/content/search/author?query=AU-ID({author_id})"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": SCOPUS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        author_info = data["search-results"]["entry"][0]
        return author_info
    except requests.exceptions.RequestException as e:
        return None

# extract_author_info_by_name function to search using both first and last names
def extract_author_info_by_name(author_name):
    # Split the input into first and last names
    parts = author_name.split()
    if len(parts) != 2:
        return []

    first_name, last_name = parts[0], parts[1]

    url = f"https://api.elsevier.com/content/search/author?query=AUTHFIRST({first_name})+AND+AUTHLAST({last_name})"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": SCOPUS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        authors = data["search-results"]["entry"]
        return authors
    except requests.exceptions.RequestException as e:
        return []

# Define a function to extract document information from Scopus
def extract_document_info(document_id):
    url = f"https://api.elsevier.com/content/abstract/scopus_id/{document_id}"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": SCOPUS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        doc_info = data["abstracts-retrieval-response"]["coredata"]
        return doc_info
    except requests.exceptions.RequestException as e:
        return None

# Define a function to extract author metrics from Scopus
def extract_author_metrics(author_id):
    url = f"https://api.elsevier.com/content/author/metrics?author_id={author_id}"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": SCOPUS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        metrics = data.get("author-retrieval-response", {}).get("coredata", {})
        return metrics
    except requests.exceptions.RequestException as e:
        return {}

# Define a command handler to start the bot and initiate the conversation
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to the Scopus Author Info bot! Please choose how you want to search for information:",
                              reply_markup=ReplyKeyboardMarkup([["Search by Name", "Search by ID", "Search by Document"]], one_time_keyboard=True))
    return SEARCH_BY_NAME_ID

# Function to handle the user's choice of search
def search_choice(update: Update, context: CallbackContext):
    user_choice = update.message.text

    if user_choice == "Search by Name":
        update.message.reply_text("Please enter the author's first name and last name (e.g., Mujib Rabin):")
        return SEARCH_BY_NAME
    elif user_choice == "Search by ID":
        update.message.reply_text("Please enter the author's Scopus ID:")
        return SEARCH_BY_ID
    elif user_choice == "Search by Document":
        update.message.reply_text("Please enter the document ID:")
        return SEARCH_BY_DOCUMENT

# search_by_name function to handle multiple authors and user choice
def search_by_name(update: Update, context: CallbackContext):
    author_name = update.message.text
    authors = extract_author_info_by_name(author_name)

    if authors:
        # Prepare a list of author names for the user to choose from
        author_names = [f"{author['preferred-name']['given-name']} {author['preferred-name']['surname']}" for author in authors]
        update.message.reply_text("Multiple authors found with the same name. Please choose an author by typing its number:\n\n" +
                                  "\n".join([f"{index + 1}. {name}" for index, name in enumerate(author_names)]))

        # Set the list of authors and the state in the user's context
        context.user_data['authors'] = authors
        return SEARCH_BY_NAME_ID
    else:
        update.message.reply_text("Author information not found or an error occurred. Please check the author name and try again.")

    return ConversationHandler.END

# Modify the search_choice function to handle the case where the user chooses a number for the author
def search_choice(update: Update, context: CallbackContext):
    user_choice = update.message.text

    # Check if the user's choice is a number
    if user_choice.isdigit():
        index = int(user_choice) - 1
        authors = context.user_data.get('authors')

        if 0 <= index < len(authors):
            # Get the selected author and proceed with displaying their information
            author_info = authors[index]
            author_id = author_info['dc:identifier']
            
            # Extract additional information
            documents = extract_author_documents(author_id)
            metrics = extract_author_metrics(author_id)
            
            # Prepare a response with author information
            response = f"Author ID: {author_id}\n"
            response += f"Author Name: {author_info['preferred-name']['given-name']} {author_info['preferred-name']['surname']}\n"
            response += f"Affiliation: {author_info['affiliation-current']['affiliation-name']}\n"
            response += f"City: {author_info['affiliation-current']['affiliation-city']}\n"
            response += f"Country: {author_info['affiliation-current']['affiliation-country']}\n"
            response += f"ORCID: {author_info.get('orcid', 'N/A')}\n"
            response += "Subject Areas:\n"

            for subject_area in author_info.get('subject-area', []):
                response += f"- {subject_area['$']} (Frequency: {subject_area.get('@frequency', 'N/A')})\n"

            # Add documents
            if documents:
                response += "\nDocuments:\n"
                for document in documents:
                    response += f"- Document ID: {document['document-id']}, Title: {document['title']}\n"
            
            # Add metrics
            if metrics:
                response += "\nMetrics:\n"
                response += f"- H-Index: {metrics.get('h-index', 'N/A')}\n"
                response += f"- Citation Count: {metrics.get('citation-count', 'N/A')}\n"

            # Send the response to the user
            update.message.reply_text(response)
        else:
            update.message.reply_text("Invalid author number. Please choose a valid number.")
    elif user_choice == "Search by Name":
        update.message.reply_text("Please enter the author's first name and last name (e.g., Mujib Rabin):")
        return SEARCH_BY_NAME
    elif user_choice == "Search by ID":
        update.message.reply_text("Please enter the author's Scopus ID:")
        return SEARCH_BY_ID
    elif user_choice == "Search by Document":
        update.message.reply_text("Please enter the document ID:")
        return SEARCH_BY_DOCUMENT
    else:
        update.message.reply_text("Invalid choice. Please choose an option or select another option.")

    return ConversationHandler.END

# Function to handle the ID search
def search_by_id(update: Update, context: CallbackContext):
    author_id = update.message.text
    author_info = extract_author_info(author_id)

    if author_info:
        # Prepare a response with author information
        response = f"Author ID: {author_id}\n"
        response += f"Author Name: {author_info['preferred-name']['given-name']} {author_info['preferred-name']['surname']}\n"
        response += f"Affiliation: {author_info['affiliation-current']['affiliation-name']}\n"
        response += f"City: {author_info['affiliation-current']['affiliation-city']}\n"
        response += f"Country: {author_info['affiliation-current']['affiliation-country']}\n"
        response += f"ORCID: {author_info.get('orcid', 'N/A')}\n"
        response += "Subject Areas:\n"

        for subject_area in author_info.get('subject-area', []):
            response += f"- {subject_area['$']} (Frequency: {subject_area.get('@frequency', 'N/A')})\n"

        # Get document information for the author
        documents = extract_author_documents(author_id)
        if documents:
            response += "\nDocuments:\n"
            for document in documents:
                response += f"- Document ID: {document['document-id']}, Title: {document['title']}\n"
        
        # Get metrics for the author
        metrics = extract_author_metrics(author_id)
        if metrics:
            response += "\nMetrics:\n"
            response += f"- H-Index: {metrics.get('h-index', 'N/A')}\n"
            response += f"- Citation Count: {metrics.get('citation-count', 'N/A')}\n"

        # Send the response to the user
        update.message.reply_text(response)
    else:
        update.message.reply_text("Author information not found or an error occurred. Please check the author ID and try again.")

    return ConversationHandler.END

# Function to extract all documents for an author
def extract_author_documents(author_id):
    url = f"https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": SCOPUS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        documents = []

        for entry in data["search-results"]["entry"]:
            documents.append({
                "document-id": entry["dc:identifier"],
                "title": entry.get("dc:title", "N/A")
            })

        return documents
    except requests.exceptions.RequestException as e:
        return None

# Function to handle the document search
def search_by_document(update: Update, context: CallbackContext):
    document_id = update.message.text
    doc_info = extract_document_info(document_id)

    if doc_info:
        # Prepare a response with document information, including the abstract
        response = f"Document ID: {document_id}\n"
        response += f"Title: {doc_info.get('dc:title', 'N/A')}\n"
        response += f"Authors: {', '.join(doc_info.get('dc:creator', ['N/A']))}\n"
        response += f"Publication Date: {doc_info.get('prism:coverDate', 'N/A')}\n"
        response += f"Source Title: {doc_info.get('prism:publicationName', 'N/A')}\n"
        response += f"Abstract: {doc_info.get('dc:description', 'N/A')}\n"

        # Send the response to the user
        update.message.reply_text(response)
    else:
        update.message.reply_text("Document information not found or an error occurred. Please check the document ID and try again.")

    return ConversationHandler.END

# Main function to start the bot
def main():
    # Initialize the Telegram bot
    updater = Updater(token="6374304134:AAHXE--FYY3NrdBGvu7G8F9kSlNpUqAb9tE", use_context=True)  # Replace with your bot token
    dispatcher = updater.dispatcher

    # Define conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEARCH_BY_NAME_ID: [MessageHandler(Filters.text & ~Filters.command, search_choice)],
            SEARCH_BY_NAME: [MessageHandler(Filters.text & ~Filters.command, search_by_name)],
            SEARCH_BY_ID: [MessageHandler(Filters.text & ~Filters.command, search_by_id)],
            SEARCH_BY_DOCUMENT: [MessageHandler(Filters.text & ~Filters.command, search_by_document)],
        },
        fallbacks=[],
    )

    # Add handlers to the dispatcher
    dispatcher.add_handler(conv_handler)

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
