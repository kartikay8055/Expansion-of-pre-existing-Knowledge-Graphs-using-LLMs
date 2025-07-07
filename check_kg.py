import json
import re
import logging
import traceback
import os
from neo4j import GraphDatabase
from typing import Optional, Tuple, Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7690"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
DATABASE_NAME = "expansion"

class KnowledgeGraphUpdater:
    def __init__(self, uri: str, user: str, password: str, database: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        # Load valid relation types
        self.valid_relation_types = self.load_relation_types()
        # Test connection
        self._test_connection()
        # Initialize summary tracking
        self.total_summary = {
            'new_entities': 0,
            'updated_entities': 0,
            'new_relationships': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'entity_breakdown': {},
            'relationship_breakdown': {},
            'new_entity_details': [],
            'new_relationship_details': []
        }
        
    def _test_connection(self):
        """Test the Neo4j connection."""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1").single()
            logging.info("Neo4j connection successful")
        except Exception as e:
            logging.error(f"Failed to connect to Neo4j: {e}")
            raise
        
    def load_relation_types(self) -> List[str]:
        """Load valid relation types from JSON file."""
        try:
            # Try to load from project directory first
            relation_files = [
                './relation_types.json',
                '../relation_types.json',
                os.path.expanduser('~/thesis/relation_types.json')
            ]
            
            for file_path in relation_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        return json.load(f)
                        
        except Exception as e:
            logging.warning(f"Could not load relation_types.json: {e}")
            
        logging.warning("relation_types.json not found. Using default relation types.")
        return [
                "RELATED_GENETIC_DISORDER",
                "COMPLEX_IN_PATHWAY",
                "PROTEIN_DISEASE_ASSOCIATION",
                "DDI",
                "DRUG_PATHWAY_ASSOCIATION",
                "PPI",
                "DISEASE_PATHWAY_ASSOCIATION",
                "DRUG_TARGET",
                "DRUG_CARRIER",
                "DRUG_ENZYME",
                "DRUG_TRANSPORTER",
                "DISEASE_GENETIC_DISORDER",
                "DRUG_DISEASE_ASSOCIATION",
                "PROTEIN_PATHWAY_ASSOCIATION",
                "COMPLEX_TOP_LEVEL_PATHWAY",
                "DPI"
            ]
    
    def validate_relation_type(self, rel_type: str) -> str:
        """Validate and standardize relation type."""
        if not rel_type or not rel_type.strip():
            logging.warning("Empty relation type provided")
            return "RELATIONSHIP"
            
        if rel_type in self.valid_relation_types:
            return rel_type
        
        # Try to find a close match (case-insensitive)
        rel_type_upper = rel_type.upper()
        for valid_rel in self.valid_relation_types:
            if valid_rel.upper() == rel_type_upper:
                return valid_rel
        
        logging.warning(f"Unknown relation type: {rel_type}. Using as-is.")
        return rel_type
        
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
    
    def clean_json_string(self, json_str: str) -> str:
        """Clean JSON string by removing markdown code block syntax."""
        if not json_str:
            return ""
        return re.sub(r'```json\n|\n```', '', json_str.strip())
    
    def entity_exists(self, tx, entity_name: str, entity_type: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Check if an entity already exists using EXACT case-insensitive matching."""
        if not entity_name or not entity_name.strip():
            return None, None
            
        # Map entity types to your actual Neo4j labels
        label_mapping = {
            "drug": "DRUG",             
            "medication": "DRUG",       
            "chemical": "DRUG",         
            "disease": "DISEASE",        
            "gene": "Gene",             
            "protein": "PROTEIN",       
            "gene_protein": "Gene"      
        }
        
        normalized_entity_type = entity_type.lower()
        label = label_mapping.get(normalized_entity_type, entity_type.upper())
        
        query = f"""
        MATCH (n:{label})
        WHERE (
            // Check for exact match in NAME array (case-insensitive)
            (n.NAME IS NOT NULL AND 
             any(item IN n.NAME WHERE toLower(toString(item)) = toLower($name)))
        )
        RETURN n, elementId(n) as node_id
        LIMIT 1
        """
        
        try:
            result = tx.run(query, name=entity_name.strip())
            record = result.single()
            if record:
                return record["node_id"], record["n"]
        except Exception as e:
            logging.error(f"Error checking entity existence for {entity_name}: {e}")
        
        return None, None

    def relationship_exists(self, tx, entity1_name: str, entity2_name: str, rel_type: str) -> bool:
        """Check if a relationship already exists (bidirectional check)."""
        if not all([entity1_name, entity2_name, rel_type]):
            return False
            
        query = f"""
        MATCH (a)-[r:`{rel_type}`]-(b)
        WHERE (
            // Check both directions
            (
                (a.NAME IS NOT NULL AND 
                 any(item IN a.NAME WHERE toLower(toString(item)) = toLower($name1)))
                AND
                (b.NAME IS NOT NULL AND 
                 any(item IN b.NAME WHERE toLower(toString(item)) = toLower($name2)))
            )
            OR
            (
                (a.NAME IS NOT NULL AND 
                 any(item IN a.NAME WHERE toLower(toString(item)) = toLower($name2)))
                AND
                (b.NAME IS NOT NULL AND 
                 any(item IN b.NAME WHERE toLower(toString(item)) = toLower($name1)))
            )
        )
        RETURN count(r) > 0 as exists
        """
        
        try:
            result = tx.run(query, name1=entity1_name.strip(), name2=entity2_name.strip())
            return result.single()["exists"]
        except Exception as e:
            logging.error(f"Error checking relationship existence: {e}")
            return False
        
    def update_existing_entity(self, tx, entity_name: str, entity_type: str, entity_id: Optional[str], node_id: str):
        """Update an existing entity by appending new data to arrays."""
        if not entity_name or not node_id:
            return None
            
        try:
            if entity_id and entity_id.strip() and entity_id != "Not specified":
                update_query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                SET 
                    // Handle source array
                    n.source = CASE 
                        WHEN n.source IS NULL THEN ['pubtator_extraction']
                        WHEN 'pubtator_extraction' IN n.source THEN n.source
                        ELSE n.source + ['pubtator_extraction'] END,
                    
                    // Handle NAME array - only add if not already present
                    n.NAME = CASE 
                        WHEN n.NAME IS NULL THEN [$new_name]
                        WHEN any(item IN n.NAME WHERE toLower(toString(item)) = toLower($new_name)) THEN n.NAME
                        ELSE n.NAME + [$new_name] END,
                    
                    // Handle id array - only add if not already present
                    n.id = CASE 
                        WHEN n.id IS NULL THEN [$new_id]
                        WHEN $new_id IN n.id THEN n.id
                        ELSE n.id + [$new_id] END
                RETURN n
                """
                result = tx.run(update_query, node_id=node_id, new_name=entity_name.strip(), new_id=entity_id.strip())
            else:
                update_query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                SET 
                    // Handle source array
                    n.source = CASE 
                        WHEN n.source IS NULL THEN ['pubtator_extraction']
                        WHEN 'pubtator_extraction' IN n.source THEN n.source
                        ELSE n.source + ['pubtator_extraction'] END,
                    
                    // Handle NAME array - only add if not already present
                    n.NAME = CASE 
                        WHEN n.NAME IS NULL THEN [$new_name]
                        WHEN any(item IN n.NAME WHERE toLower(toString(item)) = toLower($new_name)) THEN n.NAME
                        ELSE n.NAME + [$new_name] END
                RETURN n
                """
                result = tx.run(update_query, node_id=node_id, new_name=entity_name.strip())
            
            return result.single()
        except Exception as e:
            logging.error(f"Error updating entity {entity_name}: {e}")
            return None

    def create_new_entity(self, tx, entity_name: str, entity_type: str, entity_id: Optional[str]):
        """Create a new entity with array properties."""
        if not entity_name or not entity_name.strip():
            return None
            
        label_mapping = {
            "drug": "DRUG",             
            "medication": "DRUG",       
            "chemical": "DRUG",         
            "disease": "DISEASE",        
            "gene": "Gene",             
            "protein": "PROTEIN",       
            "gene_protein": "Gene"      
        }
        
        normalized_entity_type = entity_type.lower()
        label = label_mapping.get(normalized_entity_type)
        
        if label is None:
            logging.warning(f"Unmapped entity_type '{entity_type}'. Defaulting label to its uppercase form: {entity_type.upper()}")
            label = entity_type.upper()

        try:
            if entity_id and entity_id.strip() and entity_id != "Not specified":
                query = f"""
                CREATE (n:{label})
                SET n.NAME = [$name], 
                    n.id = [$id], 
                    n.source = ['pubtator_extraction']
                RETURN n
                """
                result = tx.run(query, name=entity_name.strip(), id=entity_id.strip())
            else:
                query = f"""
                CREATE (n:{label})
                SET n.NAME = [$name], 
                    n.source = ['pubtator_extraction']
                RETURN n
                """
                result = tx.run(query, name=entity_name.strip())
            
            return result.single()
        except Exception as e:
            logging.error(f"Error creating entity {entity_name}: {e}")
            return None
    
    def create_relationship(self, tx, entity1_name: str, entity2_name: str, rel_type: str):
        """Create a new relationship between two entities using exact matching."""
        if not all([entity1_name, entity2_name, rel_type]):
            return None
            
        # Validate relation type
        validated_rel_type = self.validate_relation_type(rel_type)
        
        query = f"""
        MATCH (a), (b)
        WHERE (
            // Exact match for entity 1
            (a.NAME IS NOT NULL AND 
             any(item IN a.NAME WHERE toLower(toString(item)) = toLower($name1)))
        )
        AND (
            // Exact match for entity 2
            (b.NAME IS NOT NULL AND 
             any(item IN b.NAME WHERE toLower(toString(item)) = toLower($name2)))
        )
        WITH a, b LIMIT 1
        CREATE (a)-[r:`{validated_rel_type}`]->(b)
        SET r.source = ['pubtator_extraction']
        RETURN r
        """
        
        try:
            result = tx.run(query, name1=entity1_name.strip(), name2=entity2_name.strip())
            return result.single()
        except Exception as e:
            logging.error(f"Failed to create relationship {entity1_name} -> {entity2_name}: {e}")
            return None

    def extract_entities_from_relationship(self, rel: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Extract entity names from relationship dictionary with improved logic."""
        entity1_name = None
        entity2_name = None
        
        try:
            # Handle different relationship patterns
            if "drug" in rel and "disease" in rel:
                drug = rel["drug"]
                disease = rel["disease"]
                entity1_name = drug.get("name", drug) if isinstance(drug, dict) else str(drug)
                entity2_name = disease.get("name", disease) if isinstance(disease, dict) else str(disease)
                
            elif "drug" in rel and "gene" in rel:
                drug = rel["drug"]
                gene = rel["gene"]
                entity1_name = drug.get("name", drug) if isinstance(drug, dict) else str(drug)
                entity2_name = gene.get("name", gene) if isinstance(gene, dict) else str(gene)
                
            elif "gene" in rel and "disease" in rel:
                gene = rel["gene"]
                disease = rel["disease"]
                entity1_name = gene.get("name", gene) if isinstance(gene, dict) else str(gene)
                entity2_name = disease.get("name", disease) if isinstance(disease, dict) else str(disease)
                
            elif "protein" in rel and "disease" in rel:
                protein = rel["protein"]
                disease = rel["disease"]
                entity1_name = protein.get("name", protein) if isinstance(protein, dict) else str(protein)
                entity2_name = disease.get("name", disease) if isinstance(disease, dict) else str(disease)
                
            elif "drug" in rel and "protein" in rel:
                drug = rel["drug"]
                protein = rel["protein"]
                entity1_name = drug.get("name", drug) if isinstance(drug, dict) else str(drug)
                entity2_name = protein.get("name", protein) if isinstance(protein, dict) else str(protein)
                
            elif "drug1" in rel and "drug2" in rel:  # DDI
                drug1 = rel["drug1"]
                drug2 = rel["drug2"]
                entity1_name = drug1.get("name", drug1) if isinstance(drug1, dict) else str(drug1)
                entity2_name = drug2.get("name", drug2) if isinstance(drug2, dict) else str(drug2)
                
            elif "pathway" in rel:
                # Handle pathway relationships
                pathway = rel["pathway"]
                other_entity = None
                for k, v in rel.items():
                    if k not in ["pathway", "kg_relation_type"]:
                        other_entity = v
                        break
                if other_entity:
                    entity1_name = pathway.get("name", pathway) if isinstance(pathway, dict) else str(pathway)
                    entity2_name = other_entity.get("name", other_entity) if isinstance(other_entity, dict) else str(other_entity)
                    
            else:
                # Handle protein-protein interactions more carefully
                protein_keys = [k for k in rel.keys() if "protein" in k.lower() and k != "kg_relation_type"]
                if len(protein_keys) >= 2:
                    protein1 = rel[protein_keys[0]]
                    protein2 = rel[protein_keys[1]]
                    entity1_name = protein1.get("name", protein1) if isinstance(protein1, dict) else str(protein1)
                    entity2_name = protein2.get("name", protein2) if isinstance(protein2, dict) else str(protein2)
                else:
                    # Generic fallback - try to find two entities in the relationship
                    entities_found = []
                    for k, v in rel.items():
                        if k != "kg_relation_type" and v is not None:
                            if isinstance(v, dict):
                                name = v.get("name", str(v))
                            else:
                                name = str(v)
                            if name.strip():
                                entities_found.append(name.strip())
                    
                    if len(entities_found) >= 2:
                        entity1_name = entities_found[0]
                        entity2_name = entities_found[1]
            
            # Clean and validate entity names
            if entity1_name:
                entity1_name = entity1_name.strip()
            if entity2_name:
                entity2_name = entity2_name.strip()
                
            return entity1_name, entity2_name
            
        except Exception as e:
            logging.error(f"Error extracting entities from relationship: {e}")
            return None, None

    def process_document_data(self, doc_data: Dict[str, Any]):
        """Process a single document's extracted data and add to knowledge graph."""
        doc_id = doc_data.get("document_id", "Unknown")
        json_str = doc_data.get("analysis", "")
        
        if not json_str:
            logging.warning(f"No analysis data found for document {doc_id}")
            return
        
        # Clean and parse the JSON
        clean_json = self.clean_json_string(json_str)
        try:
            data = json.loads(clean_json)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON for document {doc_id}: {e}")
            raise  # Re-raise to be caught in main() for failed document tracking
        
        logging.info(f"\nProcessing document: {doc_id}")
        
        # Debug: Show what relationship keys are available
        logging.info(f"Available relationship keys in document {doc_id}:")
        for key in data.keys():
            if key.endswith('_relationships') or 'relationship' in key.lower():
                rel_count = len(data[key]) if isinstance(data[key], list) else 0
                logging.info(f"  - {key}: {rel_count} relationships")
        
        # Track what we've added
        new_entities = 0
        updated_entities = 0
        new_relationships = 0
        
        with self.driver.session(database=self.database) as session:
            # Process entities
            entity_types = [
                ("medications", "drug"),
                ("medication_entities", "drug"), 
                ("diseases", "disease"),
                ("disease_entities", "disease"),
                ("genes", "gene"),
                ("genes_proteins", "gene"),
                ("gene_protein_entities", "gene")
            ]
            
            for entity_key, entity_type in entity_types:
                entities = data.get(entity_key, [])
                if not isinstance(entities, list):
                    continue
                    
                for entity in entities:
                    if not isinstance(entity, dict):
                        continue
                        
                    entity_name = entity.get("name", "").strip()
                    entity_id = entity.get("id", None)
                    
                    if entity_name and entity_name != "Unknown":
                        try:
                            # Check if entity exists first
                            existing_node_id, existing_node = session.execute_read(
                                self.entity_exists, entity_name, entity_type
                            )
                            
                            if existing_node_id:
                                # Entity exists - update it
                                session.execute_write(
                                    self.update_existing_entity, entity_name, entity_type, entity_id, existing_node_id
                                )
                                updated_entities += 1
                                self.total_summary['updated_entities'] += 1
                                logging.info(f"  {entity_type.capitalize()} already exists: {entity_name}")
                            else:
                                # Entity doesn't exist - create new one
                                session.execute_write(
                                    self.create_new_entity, entity_name, entity_type, entity_id
                                )
                                new_entities += 1
                                self.total_summary['new_entities'] += 1
                                
                                # Track entity type breakdown
                                if entity_type not in self.total_summary['entity_breakdown']:
                                    self.total_summary['entity_breakdown'][entity_type] = 0
                                self.total_summary['entity_breakdown'][entity_type] += 1
                                
                                # Track new entity details
                                self.total_summary['new_entity_details'].append({
                                    'name': entity_name,
                                    'type': entity_type,
                                    'id': entity_id,
                                    'document': doc_id
                                })
                                
                                logging.info(f"  Added new {entity_type}: {entity_name}")
                        except Exception as e:
                            logging.error(f"  Error processing entity {entity_name}: {e}")
            
            # Process relationships with improved mapping
            relationship_mappings = {
                "drug_disease_relationships": "DRUG_DISEASE_ASSOCIATION",
                "drug_gene_relationships": "DPI", 
                "gene_disease_relationships": "PROTEIN_DISEASE_ASSOCIATION",
                "protein_disease_relationships": "PROTEIN_DISEASE_ASSOCIATION",
                "drug_drug_relationships": "DDI",
                "drug_interaction_relationships": "DDI",
                "protein_protein_relationships": "PPI",
                "gene_gene_relationships": "PPI",
                "drug_target_relationships": "DRUG_TARGET",
                "drug_carrier_relationships": "DRUG_CARRIER",
                "drug_enzyme_relationships": "DRUG_ENZYME",
                "drug_transporter_relationships": "DRUG_TRANSPORTER",
                "drug_pathway_relationships": "DRUG_PATHWAY_ASSOCIATION",
                "disease_pathway_relationships": "DISEASE_PATHWAY_ASSOCIATION",
                "protein_pathway_relationships": "PROTEIN_PATHWAY_ASSOCIATION",
                "genetic_disorder_relationships": "RELATED_GENETIC_DISORDER",
                "disease_genetic_relationships": "DISEASE_GENETIC_DISORDER",
                "pathway_complex_relationships": "COMPLEX_IN_PATHWAY",
                "top_level_pathway_relationships": "COMPLEX_TOP_LEVEL_PATHWAY",
            }
            
            # Process all relationship keys found in the data
            for key, relationships in data.items():
                if not ((key.endswith('_relationships') or 'relationship' in key.lower()) and isinstance(relationships, list)):
                    continue
                    
                # Get default relationship type from mapping or use a generic one
                default_rel_type = relationship_mappings.get(key, "RELATIONSHIP")
                
                logging.info(f"Processing {len(relationships)} relationships from key: {key}")
                
                for rel in relationships:
                    if not isinstance(rel, dict):
                        continue
                        
                    # Get the knowledge graph relation type if specified
                    kg_rel_type = rel.get("kg_relation_type", default_rel_type)
                    if kg_rel_type == "Not specified" or not kg_rel_type:
                        kg_rel_type = default_rel_type
                    
                    # Validate the relation type
                    validated_rel_type = self.validate_relation_type(kg_rel_type)
                    
                    # Extract entity names from relationship
                    entity1_name, entity2_name = self.extract_entities_from_relationship(rel)
                    
                    if entity1_name and entity2_name:
                        try:
                            # Check if relationship exists
                            exists = session.execute_read(
                                self.relationship_exists, entity1_name, entity2_name, validated_rel_type
                            )
                            
                            if not exists:
                                # Create new relationship
                                result = session.execute_write(
                                    self.create_relationship, entity1_name, entity2_name, validated_rel_type
                                )
                                if result:
                                    new_relationships += 1
                                    self.total_summary['new_relationships'] += 1
                                    
                                    # Track relationship type breakdown
                                    if validated_rel_type not in self.total_summary['relationship_breakdown']:
                                        self.total_summary['relationship_breakdown'][validated_rel_type] = 0
                                    self.total_summary['relationship_breakdown'][validated_rel_type] += 1
                                    
                                    # Track new relationship details
                                    self.total_summary['new_relationship_details'].append({
                                        'entity1': entity1_name,
                                        'entity2': entity2_name,
                                        'type': validated_rel_type,
                                        'document': doc_id
                                    })
                                    
                                    logging.info(f"  Added new relationship: {entity1_name} --{validated_rel_type}--> {entity2_name}")
                            else:
                                logging.info(f"  Relationship already exists: {entity1_name} --{validated_rel_type}--> {entity2_name}")
                        except Exception as e:
                            logging.error(f"  Error processing relationship: {e}")
                    else:
                        logging.warning(f"  Could not extract entity names from relationship in {key}: {rel}")
        
        logging.info(f"Document {doc_id} processing complete:")
        logging.info(f"  New entities added: {new_entities}")
        if updated_entities > 0:
            logging.info(f"  Existing entities updated: {updated_entities}")
        logging.info(f"  New relationships added: {new_relationships}")
        
        # Update document processing count
        self.total_summary['processed_documents'] += 1


    def mark_document_failed(self):
        """Mark a document as failed for summary tracking."""
        self.total_summary['failed_documents'] += 1
    
    def print_comprehensive_summary(self):
        """Print a comprehensive summary of all changes made to the knowledge graph."""
        summary = self.total_summary
        
        print("\n" + "="*80)
        print("                    KNOWLEDGE GRAPH UPDATE SUMMARY")
        print("="*80)
        
        # Overall statistics
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   • Documents processed successfully: {summary['processed_documents']}")
        if summary['failed_documents'] > 0:
            # print(f"   • Documents failed: {summary['failed_documents']}")
            print(f"   • Total new entities added: {summary['new_entities']}")
        print(f"   • Total existing entities updated: {summary['updated_entities']}")
        print(f"   • Total new relationships added: {summary['new_relationships']}")
        
        # Entity breakdown
        if summary['entity_breakdown']:
            print(f"\n🧬 NEW ENTITIES BY TYPE:")
            for entity_type, count in sorted(summary['entity_breakdown'].items()):
                print(f"   • {entity_type.upper()}: {count}")
        
        # Relationship breakdown
        if summary['relationship_breakdown']:
            print(f"\n🔗 NEW RELATIONSHIPS BY TYPE:")
            for rel_type, count in sorted(summary['relationship_breakdown'].items()):
                print(f"   • {rel_type}: {count}")
        
        # Detailed new entities (show first 20, then summary)
        if summary['new_entity_details']:
            print(f"\n📋 NEW ENTITIES ADDED (showing first 20):")
            for i, entity in enumerate(summary['new_entity_details'][:20]):
                entity_id_str = f" (ID: {entity['id']})" if entity['id'] else ""
                print(f"   {i+1:2d}. {entity['name']} [{entity['type'].upper()}]{entity_id_str}")
                print(f"       └─ From document: {entity['document']}")
            
            if len(summary['new_entity_details']) > 20:
                remaining = len(summary['new_entity_details']) - 20
                print(f"       ... and {remaining} more entities")
        
        # Detailed new relationships (show first 20, then summary)
        if summary['new_relationship_details']:
            print(f"\n🔗 NEW RELATIONSHIPS ADDED (showing first 20):")
            for i, rel in enumerate(summary['new_relationship_details'][:20]):
                print(f"   {i+1:2d}. {rel['entity1']} --[{rel['type']}]--> {rel['entity2']}")
                print(f"       └─ From document: {rel['document']}")
            
            if len(summary['new_relationship_details']) > 20:
                remaining = len(summary['new_relationship_details']) - 20
                print(f"       ... and {remaining} more relationships")
        
        # Knowledge graph impact
        print(f"\n🎯 KNOWLEDGE GRAPH IMPACT:")
        total_new_items = summary['new_entities'] + summary['new_relationships']
        if total_new_items > 0:
            print(f"   • Total new items added to knowledge graph: {total_new_items}")
            entity_percentage = (summary['new_entities'] / total_new_items) * 100
            rel_percentage = (summary['new_relationships'] / total_new_items) * 100
            print(f"   • Entities vs Relationships ratio: {entity_percentage:.1f}% / {rel_percentage:.1f}%")
        
        if summary['updated_entities'] > 0:
            print(f"   • Entities enriched with additional data: {summary['updated_entities']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if summary['new_entities'] > summary['new_relationships']:
            print("   • Consider reviewing entity extraction - many entities without relationships detected")
        elif summary['new_relationships'] > summary['new_entities'] * 2:
            print("   • Good relationship extraction - knowledge graph connectivity improved significantly")
        
        # if summary['failed_documents'] > 0:
        #     failure_rate = (summary['failed_documents'] / (summary['processed_documents'] + summary['failed_documents'])) * 100
        #     print(f"   • Document failure rate: {failure_rate:.1f}% - consider reviewing failed documents")
        
        print("\n" + "="*80)
        print("                         UPDATE COMPLETED")
        print("="*80 + "\n")


def main():
    # Load the analysis results
    analysis_file = input("Enter path to analysis results JSON file: ") or "./analysis_results.json"
    
    if not analysis_file:
        logging.error("Analysis file path not provided")
        return
    
    logging.info(f"Loading analysis results from {analysis_file}...")
    
    try:
        with open(analysis_file, 'r') as f:
            analysis_results = json.load(f)
    except FileNotFoundError:
        logging.error(f"Analysis file not found: {analysis_file}")
        return
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing analysis file: {e}")
        return
    
    if not isinstance(analysis_results, list):
        logging.error("Analysis results should be a list of documents")
        return
    
    logging.info(f"Found {len(analysis_results)} documents to process")
    
    # Connect to Neo4j and process the data
    updater = None
    try:
        updater = KnowledgeGraphUpdater(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATABASE_NAME)
        
        for i, doc_data in enumerate(analysis_results, 1):
            logging.info(f"\n=== Processing document {i}/{len(analysis_results)} ===")
            try:
                updater.process_document_data(doc_data)
            except Exception as e:
                logging.error(f"Failed to process document {i}: {e}")
                updater.mark_document_failed()
        
        # Print comprehensive summary
        updater.print_comprehensive_summary()
        
    except Exception as e:
        logging.error(f"Error during knowledge graph update: {e}")
        logging.error(traceback.format_exc())
    finally:
        if updater:
            updater.close()

if __name__ == "__main__":
    main()