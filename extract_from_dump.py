import json
import csv
from neo4j import GraphDatabase
import sys

# Update these with your Neo4j connection details
NEO4J_URI = "bolt://localhost:7690"  # Keep your specified port
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
DATABASE_NAME = "expansion"  # Specify your database name

# Connect to Neo4j
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # Verify connection
    driver.verify_connectivity()
    print("Successfully connected to Neo4j")
except Exception as e:
    print(f"Failed to connect to Neo4j: {e}")
    sys.exit(1)

def extract_nodes(tx):
    # Query to extract node id, labels, and properties
    query = "MATCH (n) RETURN id(n) AS node_id, labels(n) AS labels, properties(n) AS properties"
    result = list(tx.run(query))
    print(f"Found {len(result)} nodes")
    return result

def write_nodes_to_json(nodes, output_file):
    # Convert Neo4j records to a list of dictionaries
    nodes_data = []
    for record in nodes:
        nodes_data.append({
            "node_id": record["node_id"],
            "labels": record["labels"],
            "properties": record["properties"]
        })
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(nodes_data, f, indent=2, ensure_ascii=False)
    
    print(f"Nodes extracted and written to {output_file}")

if __name__ == "__main__":
    try:
        
        with driver.session(database=DATABASE_NAME) as session:
            nodes = session.read_transaction(extract_nodes)
        
        if not nodes:
            print("No nodes were found in the database. Is your database empty?")
        else:
            output_file = "extracted_nodes.tsv"
            write_nodes_to_json(nodes, output_file)
    except Exception as e:
        print(f"Error during extraction: {e}")
    finally:
        driver.close()