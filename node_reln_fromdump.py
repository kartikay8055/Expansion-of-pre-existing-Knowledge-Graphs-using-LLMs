import json
from neo4j import GraphDatabase
import sys

# Update these with your Neo4j connection details
NEO4J_URI = "bolt://localhost:7690"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
DATABASE_NAME = "expansion"

# Connect to Neo4j
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Successfully connected to Neo4j")
except Exception as e:
    print(f"Failed to connect to Neo4j: {e}")
    sys.exit(1)

def extract_relation_types(tx):
    # Query to extract all unique relation types
    query = "MATCH ()-[r]->() RETURN DISTINCT type(r) AS relation_type"
    result = list(tx.run(query))
    relation_types = [record["relation_type"] for record in result]
    print(f"Found {len(relation_types)} relation types")
    return relation_types

def write_relations_to_json(relations, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(relations, f, indent=2, ensure_ascii=False)
    print(f"Relation types written to {output_file}")

if __name__ == "__main__":
    try:
        with driver.session(database=DATABASE_NAME) as session:
            relation_types = session.read_transaction(extract_relation_types)
        if not relation_types:
            print("No relation types found in the database.")
        else:
            output_file = "relation_types.json"
            write_relations_to_json(relation_types, output_file)
    except Exception as e:
        print(f"Error during extraction: {e}")
    finally:
        driver.close()