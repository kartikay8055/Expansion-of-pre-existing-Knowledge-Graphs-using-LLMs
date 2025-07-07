import os
import time
import logging
from pymongo import MongoClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Connect to MongoDB
try:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:28017/")
    logger.info("Connecting to MongoDB...")
    client = MongoClient(mongo_uri)
    db = client["pubtator"]
    collection = db["PubTator3"]
    logger.info("Connected to MongoDB.")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    exit(1)

# Create necessary index for performance
collection.create_index("passages.annotations.infons.identifier")
logger.info("Index created on 'passages.annotations.infons.identifier'.")

# Timer start
start_time = time.time()

# Define filter for documents related to humans
human_filter = {
    "passages.annotations": {
         "$elemMatch": {
             "$or": [
                {"infons.identifier": "9606"},
                {"infons.text": {"$regex": "Humans", "$options": "i"}},
                {"infons.type": "Species"}
             ]
         }
    }
}

# Count documents related to humans and total documents
human_count = collection.count_documents(human_filter)
total_docs = collection.count_documents({})
logger.info(f"Documents related to humans: {human_count}")
logger.info(f"Total documents before deletion: {total_docs}")

if human_count == 0:
    logger.info("No documents related to humans found. Aborting deletion.")
    exit(0)

# Build deletion query using $nor operator to keep only human-related documents
delete_query = {"$nor": [human_filter]}
logger.info("Deleting documents NOT related to humans...")

# Execute deletion
result = collection.delete_many(delete_query)
logger.info(f"Deleted {result.deleted_count} documents that are NOT related to humans.")

# Report remaining documents and elapsed time
remaining_docs = collection.count_documents({})
logger.info(f"Remaining documents in collection: {remaining_docs}")
logger.info(f"Script completed in {time.time() - start_time:.2f} seconds.")
