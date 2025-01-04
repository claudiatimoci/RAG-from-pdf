# Import Dependencies
import os
import openai
import time
from dotenv import load_dotenv

# Debugging Helper
def log(message):
    print(f"[DEBUG] {message}")

# Load environment variables from .env file
load_dotenv()
log("Environment variables loaded.")

# Check if OPENAI_API_KEY is set
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise EnvironmentError("Error: OPENAI_API_KEY is not set in the environment. Please set it in the .env file.")
log("API key loaded successfully.")

# Set OpenAI key and model
openai.api_key = openai_api_key
model_name = "gpt-4o"  # Replace with the specific GPT model you are using
log(f"Model set to: {model_name}")

# Initialize OpenAI client
try:
    client = openai.OpenAI(api_key=openai.api_key)
    log("OpenAI client initialized successfully.")
except Exception as e:
    log(f"Error initializing OpenAI client: {e}")
    raise

# Code Example: Upload PDF(s) to the OpenAI Vector Store
def upload_pdfs_to_vector_store(client, vector_store_id, directory_path):
    try:
        log(f"Uploading PDFs from directory: {directory_path}")

        if not os.path.exists(directory_path):
            raise FileNotFoundError(f"Error: Directory '{directory_path}' does not exist.")
        
        if not os.listdir(directory_path):
            raise ValueError(f"Error: Directory '{directory_path}' is empty. No files to upload.")
        
        file_ids = {}
        file_paths = [os.path.join(directory_path, file) for file in os.listdir(directory_path) if file.endswith(".pdf")]

        if not file_paths:
            raise ValueError(f"Error: No PDF files found in directory '{directory_path}'.")

        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as file:
                uploaded_file = client.beta.vector_stores.files.upload(vector_store_id=vector_store_id, file=file)
                log(f"Uploaded file: {file_name} with ID: {uploaded_file.id}")
                file_ids[file_name] = uploaded_file.id

        log(f"All files uploaded successfully to vector store with ID: {vector_store_id}")
        return file_ids

    except Exception as e:
        log(f"Error uploading files to vector store: {e}")
        return None

# Get/Create Vector Store
def get_or_create_vector_store(client, vector_store_name):
    try:
        log(f"Checking for vector store: {vector_store_name}")

        if not vector_store_name:
            raise ValueError("Error: 'vector_store_name' is not set. Please provide a valid name.")

        vector_stores = client.beta.vector_stores.list()

        for vector_store in vector_stores.data:
            if vector_store.name == vector_store_name:
                log(f"Vector Store '{vector_store_name}' already exists with ID: {vector_store.id}")
                return vector_store

        vector_store = client.beta.vector_stores.create(name=vector_store_name)
        log(f"New vector store '{vector_store_name}' created with ID: {vector_store.id}")

        upload_pdfs_to_vector_store(client, vector_store.id, 'Upload')
        return vector_store

    except Exception as e:
        log(f"Error creating or retrieving vector store: {e}")
        return None

vector_store_name = "MyVectorStore"
vector_store = get_or_create_vector_store(client, vector_store_name)

# Get/Create Assistant
def get_or_create_assistant(client, model_name, vector_store_id):
    assistant_name = "MyAssistant"
    description = "This is my AI assistant."
    instructions = "Provide helpful and accurate responses."

    try:
        log(f"Checking for assistant: {assistant_name}")

        assistants = client.beta.assistants.list()

        for assistant in assistants.data:
            if assistant.name == assistant_name:
                log(f"Assistant '{assistant_name}' already exists with ID: {assistant.id}")
                return assistant

        assistant = client.beta.assistants.create(
            model=model_name,
            name=assistant_name,
            description=description,
            instructions=instructions,
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
            temperature=0.7,
            top_p=0.9
        )
        log(f"New assistant '{assistant_name}' created with ID: {assistant.id}")
        return assistant

    except Exception as e:
        log(f"Error creating or retrieving assistant: {e}")
        return None

assistant = get_or_create_assistant(client, model_name, vector_store.id)

# Create Thread
log("Creating a new conversation thread.")
thread_conversation = {
    "tool_resources": {
        "file_search": {
            "vector_store_ids": [vector_store.id]
        }
    }
}
message_thread = client.beta.threads.create(**thread_conversation)
log(f"Thread created with ID: {message_thread.id}")

# Interact with Assistant
while True:
    user_input = input("Enter your question (or type 'exit' to quit): ")
    if user_input.lower() == 'exit':
        print("Exiting the conversation. Goodbye!")
        break

    try:
        message_conversation = {
            "role": "user",
            "content": [{"type": "text", "text": user_input}]
        }
        client.beta.threads.messages.create(thread_id=message_thread.id, **message_conversation)
        run = client.beta.threads.runs.create(thread_id=message_thread.id, assistant_id=assistant.id)

        response_text = ""
        citations = []
        processed_message_ids = set()

        while True:
            run_status = client.beta.threads.runs.retrieve(run.id, thread_id=message_thread.id)
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                raise Exception(f"Run failed: {run_status.error}")
            time.sleep(1)

        response_messages = client.beta.threads.messages.list(thread_id=message_thread.id)
        new_messages = [msg for msg in response_messages.data if msg.id not in processed_message_ids]

        for message in new_messages:
            if message.role == "assistant" and message.content:
                print(message.content[0].text)
                processed_message_ids.add(message.id)

    except Exception as e:
        log(f"Error during conversation: {e}")
