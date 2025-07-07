import os
from pymongo import MongoClient, InsertOne, UpdateOne
from lxml import etree
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:28017/")
DB_NAME = os.getenv("MONGO_DB", "pubtator")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "PubTator3")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
collection.create_index("id", unique=True)

def parse_identifier(identifier):
    """
    Parse the identifier into a database and normalized_id.
    For example, "MESH:D064420" → ("ncbi_mesh", "D064420")
    """
    if identifier and ":" in identifier:
        db_part, id_part = identifier.split(":", 1)
        db_map = {
            "MESH": "ncbi_mesh",
            "CHEBI": "chebi",
            # Add other mappings as needed
        }
        database = db_map.get(db_part, db_part.lower())
        return database, id_part
    return None, identifier

def convert_value(key, value):
    """
    Convert specific keys:
      - For 'valid', convert to boolean.
      - For 'normalized', split into a list.
    Other keys are returned as-is.
    """
    if key == "valid":
        return value.lower() == "true"
    elif key == "normalized":
        return [v.strip() for v in value.split(",")] if value else []
    return value

def parse_document(elem):
    doc_id = elem.findtext('id')
    document_data = {
        "_id": f"{doc_id}|None",
        "id": doc_id,
        "infons": {},
        "passages": [],
        "relations": []
    }
    
    # Document-level infons
    for infon in elem.findall('infon'):
        key = infon.get("key")
        value = infon.text.strip() if infon.text else ""
        document_data["infons"][key] = convert_value(key, value)
    
    # Process passages
    for passage in elem.findall('passage'):
        # Get offset either from attribute or <offset> tag
        offset = 0
        if passage.get("offset"):
            try:
                offset = int(passage.get("offset"))
            except ValueError:
                offset = 0
        else:
            offset_tag = passage.find('offset')
            if offset_tag is not None and offset_tag.text:
                try:
                    offset = int(offset_tag.text.strip())
                except ValueError:
                    offset = 0

        text_tag = passage.find('text')
        text = text_tag.text.strip() if text_tag is not None and text_tag.text else ""
        
        passage_data = {
            "infons": {},
            "offset": offset,
            "text": text,
            "sentences": [],
            "annotations": []
        }
        
        # Passage-level infons (all keys preserved)
        for infon in passage.findall('infon'):
            key = infon.get("key")
            value = infon.text.strip() if infon.text else ""
            passage_data["infons"][key] = value
        
        # Process annotations within the passage
        for annotation in passage.findall('annotation'):
            annotation_data = {
                "id": annotation.get("id"),
                "infons": {},
                "text": "",
                "locations": []
            }
            # Extract every annotation infon as-is
            for infon in annotation.findall('infon'):
                key = infon.get("key")
                value = infon.text.strip() if infon.text else ""
                annotation_data["infons"][key] = convert_value(key, value)
            
            # Get annotation text if available
            text_tag = annotation.find('text')
            if text_tag is not None and text_tag.text:
                annotation_data["text"] = text_tag.text.strip()
            
            # Process locations for the annotation
            for location in annotation.findall('location'):
                annotation_data["locations"].append({
                    "offset": int(location.get("offset", 0)),
                    "length": int(location.get("length", 0))
                })
            
            # Derive additional fields from the identifier only if not already present
            identifier = annotation_data["infons"].get("identifier", "")
            if identifier:
                database, normalized_id = parse_identifier(identifier)
                if "database" not in annotation_data["infons"]:
                    annotation_data["infons"]["database"] = database
                if "normalized_id" not in annotation_data["infons"]:
                    annotation_data["infons"]["normalized_id"] = normalized_id
                if "valid" not in annotation_data["infons"]:
                    annotation_data["infons"]["valid"] = (identifier != "-")
                if "normalized" not in annotation_data["infons"]:
                    annotation_data["infons"]["normalized"] = [normalized_id] if normalized_id else []
                if "type" in annotation_data["infons"] and "biotype" not in annotation_data["infons"]:
                    annotation_data["infons"]["biotype"] = annotation_data["infons"]["type"].lower()
            
            passage_data["annotations"].append(annotation_data)
        
        document_data["passages"].append(passage_data)
    
    # Process document-level relations, if any
    for relation in elem.findall('relation'):
        relation_data = {
            "id": relation.get("id"),
            "infons": {},
            "nodes": []
        }
        for infon in relation.findall('infon'):
            key = infon.get("key")
            value = infon.text.strip() if infon.text else ""
            relation_data["infons"][key] = value
        for node in relation.findall('node'):
            relation_data["nodes"].append({
                "ref_id": node.get("refid"),
                "role": node.get("role")
            })
        document_data["relations"].append(relation_data)
    
    return document_data

def process_xml_file(xml_file_path):
    bulk_ops = []
    try:
        # Use iterparse to stream through each <document> element.
        context = etree.iterparse(xml_file_path, events=('end',), tag='document')
        for _, elem in context:
            try:
                doc = parse_document(elem)
                # Replace InsertOne with UpdateOne for upsert behavior
                bulk_ops.append(
                    UpdateOne(
                        {"_id": doc["_id"]},  # Match by _id
                        {"$set": doc},       # Update the document
                        upsert=True          # Insert if it doesn't exist
                    )
                )
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
                if len(bulk_ops) >= 1000:
                    collection.bulk_write(bulk_ops)
                    print(f"Inserted/Updated {len(bulk_ops)} documents from {xml_file_path}")
                    bulk_ops = []
            except Exception as e:
                print(f"Error processing a document in {xml_file_path}: {e}")
        if bulk_ops:
            collection.bulk_write(bulk_ops)
            print(f"Inserted/Updated {len(bulk_ops)} remaining documents from {xml_file_path}")
    except etree.XMLSyntaxError as e:
        print(f"Error parsing file {xml_file_path}: {e}")

def process_directory(directory_path):
    """
    Process every XML file in the given directory.
    """
    files = [f for f in os.listdir(directory_path) if f.lower().endswith('.xml')]
    total_files = len(files)
    for idx, filename in enumerate(files, start=1):
        file_path = os.path.join(directory_path, filename)
        print(f"Processing {file_path} ({idx}/{total_files})...", flush=True)
        process_xml_file(file_path)

if __name__ == "__main__":
    # Allow user to specify directory path
    import sys
    if len(sys.argv) > 1:
        DIRECTORY_PATH = sys.argv[1]
    else:
        DIRECTORY_PATH = input("Enter path to PubTator XML directory: ") or "/home/kartikay23230/pubmed/output/BioCXML"
    
    print(f"Starting to process directory: {DIRECTORY_PATH}", flush=True)
    
    if not os.path.exists(DIRECTORY_PATH):
        print(f"Error: Directory {DIRECTORY_PATH} does not exist")
        exit(1)
        
    process_directory(DIRECTORY_PATH)
    print("Processing completed.", flush=True)
