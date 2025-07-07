import json
import os
import re
import io
from contextlib import redirect_stdout
from openai import OpenAI


EXISTING_RELATION_TYPES = [
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

def extract_relevant_data(document):
    """Extract the most relevant fields from a PubTator document for entity/relation extraction."""
    
    # Get basic document info
    doc_id = document.get('id', '')
    
    # Extract text content from passages
    passages_data = []
    for passage in document.get('passages', []):
        passage_info = {
            'text': passage.get('text', ''),
            'type': passage.get('infons', {}).get('section_type', passage.get('infons', {}).get('type', '')),
            'annotations': []
        }
        
        # Extract annotations (entities)
        for annotation in passage.get('annotations', []):
            entity = {
                'id': annotation.get('id', ''),
                'text': annotation.get('text', ''),
                'type': annotation.get('infons', {}).get('type', ''),
                'identifier': annotation.get('infons', {}).get('identifier', ''),
                'normalized_id': annotation.get('infons', {}).get('normalized_id', ''),
                'biotype': annotation.get('infons', {}).get('biotype', '')
            }
            passage_info['annotations'].append(entity)
        
        passages_data.append(passage_info)
    
    # Extract relations
    relations_data = []
    for relation in document.get('relations', []):
        rel = {
            'id': relation.get('id', ''),
            'type': relation.get('infons', {}).get('type', ''),
            'role1': relation.get('infons', {}).get('role1', ''),
            'role2': relation.get('infons', {}).get('role2', ''),
            'score': relation.get('infons', {}).get('score', ''),
            'nodes': relation.get('nodes', [])
        }
        relations_data.append(rel)
    
    # Compile the final structured document
    structured_doc = {
        'document_id': doc_id,
        'passages': passages_data,
        'relations': relations_data
    }
    
    return structured_doc


def process_documents(input_file, output_file=None):
    """Process all documents in the input file and save to output file."""
    with open(input_file, 'r') as f:
        documents = json.load(f)
    
    processed_docs = [extract_relevant_data(doc) for doc in documents]
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(processed_docs, f, indent=2)
    
    return processed_docs

def analyze_with_openai(processed_docs, api_key=None):
    """Send processed documents to OpenAI for analysis."""
    client = OpenAI(api_key=api_key)
    
    # Create a string of relation types for the prompt
    relation_types_str = "\n".join([f"- {rel}" for rel in EXISTING_RELATION_TYPES])
    
    results = []
    for doc in processed_docs:
        # Create a structured prompt with the document data
        prompt = f"""
Extract all biomedical entities and relationships from the following PubTator data:

Document ID: {doc['document_id']}

TEXT PASSAGES:
"""
        # Add text passages
        for i, passage in enumerate(doc['passages']):
            if passage['text']:
                prompt += f"\n[{passage['type']}]: {passage['text']}\n"
        
        prompt += "\nANNOTATED ENTITIES:\n"
        # Add all annotated entities
        for passage in doc['passages']:
            for annotation in passage['annotations']:
                if annotation['text']:
                    prompt += f"- {annotation['text']} (Type: {annotation['type']}, ID: {annotation['identifier']})\n"
        
        prompt += "\nRELATIONSHIPS:\n"
        # Add relationships
        for relation in doc['relations']:
            prompt += f"- {relation['type']} between {relation['role1']} and {relation['role2']} (Score: {relation['score']})\n"
        
        prompt += f"""
Extract and organize the following:
1. All medication entities
2. All disease entities
3. All gene/protein entities
4. Drug-disease relationships
5. Drug-gene relationships 
6. Gene-disease relationships

IMPORTANT: For each relationship, assign one of the following standardized relation types from the knowledge graph if applicable:
{relation_types_str}

If none of these existing relations match exactly, you may suggest a new relation name.

Return as JSON with these sections. For each relationship, include a "kg_relation_type" field with the appropriate relation type from the list above.
"""
        
        # Call the OpenAI API
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a biomedical entity and relationship extraction assistant specialized in knowledge graph integration."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            results.append({
                "document_id": doc['document_id'],
                "analysis": response.choices[0].message.content
            })
        except Exception as e:
            print(f"Error processing document {doc['document_id']}: {str(e)}")
            results.append({
                "document_id": doc['document_id'],
                "analysis": f"Error: {str(e)}"
            })
    
    return results

# ======== VISUALIZATION FUNCTIONS ========

def clean_json_string(json_str):
    """Cleans JSON string by removing markdown code block syntax."""
    return re.sub(r'```json\n|\n```', '', json_str)

def print_section_header(title, count=None):
    """Prints a formatted section header with optional count."""
    header = f"== {title} "
    if count is not None:
        header += f"({count}) "
    header += "=" * (60 - len(header))
    return header

def format_entity(entity, indent=2):
    """Format entity information as a string."""
    spaces = " " * indent
    lines = []
    lines.append(f"{spaces}NAME: {entity.get('name', 'Unknown')}")
    lines.append(f"{spaces}TYPE: {entity.get('type', 'Not specified')}")
    lines.append(f"{spaces}ID:   {entity.get('id', 'Not specified')}")
    lines.append("")
    return "\n".join(lines)

def format_relationship(rel, rel_type, indent=2):
    """Format a relationship as a string."""
    spaces = " " * indent
    lines = []
    
    lines.append(f"{spaces}RELATIONSHIP TYPE: {rel_type}")
    
    # Add knowledge graph relation type if available
    kg_relation = rel.get("kg_relation_type", "Not specified")
    lines.append(f"{spaces}KG RELATION: {kg_relation}")
    
    # For drug-disease relationships
    if "drug" in rel and "disease" in rel:
        drug = rel["drug"]
        disease = rel["disease"]
        
        # Handle different formats (sometimes nested dicts, sometimes direct strings)
        if isinstance(drug, dict):
            drug_name = drug.get("name", "Unknown drug")
            drug_id = drug.get("id", "Unknown ID")
        else:
            drug_name = drug
            drug_id = "Not specified"
            
        if isinstance(disease, dict):
            disease_name = disease.get("name", "Unknown disease")
            disease_id = disease.get("id", "Unknown ID")
        else:
            disease_name = disease
            disease_id = "Not specified"
            
        lines.append(f"{spaces}DRUG:    {drug_name} ({drug_id})")
        lines.append(f"{spaces}DISEASE: {disease_name} ({disease_id})")
        
    # For drug-gene relationships
    elif "drug" in rel and "gene" in rel:
        drug = rel["drug"]
        gene = rel["gene"]
        
        if isinstance(drug, dict):
            drug_name = drug.get("name", "Unknown drug")
            drug_id = drug.get("id", "Unknown ID")
        else:
            drug_name = drug
            drug_id = "Not specified"
            
        if isinstance(gene, dict):
            gene_name = gene.get("name", "Unknown gene")
            gene_id = gene.get("id", "Unknown ID")
        else:
            gene_name = gene
            gene_id = "Not specified"
            
        lines.append(f"{spaces}DRUG: {drug_name} ({drug_id})")
        lines.append(f"{spaces}GENE: {gene_name} ({gene_id})")
        
    # For gene-disease relationships
    elif "gene" in rel and "disease" in rel:
        gene = rel["gene"]
        disease = rel["disease"]
        
        if isinstance(gene, dict):
            gene_name = gene.get("name", "Unknown gene")
            gene_id = gene.get("id", "Unknown ID")
        else:
            gene_name = gene
            gene_id = "Not specified"
            
        if isinstance(disease, dict):
            disease_name = disease.get("name", "Unknown disease")
            disease_id = disease.get("id", "Unknown ID")
        else:
            disease_name = disease
            disease_id = "Not specified"
            
        lines.append(f"{spaces}GENE:    {gene_name} ({gene_id})")
        lines.append(f"{spaces}DISEASE: {disease_name} ({disease_id})")
    
    # Print relationship type if available
    if "relationship" in rel:
        relationship = rel["relationship"]
        lines.append(f"{spaces}RELATION: {relationship}")
        
    # Print score if available
    if "score" in rel:
        score = rel["score"]
        lines.append(f"{spaces}SCORE: {score}")
        
    lines.append("")
    return "\n".join(lines)

def visualize_results(doc):
    """Process a single document's analysis and return formatted text."""
    doc_id = doc["document_id"]
    json_str = doc["analysis"]
    
    # Clean and parse the JSON string
    clean_json = clean_json_string(json_str)
    try:
        data = json.loads(clean_json)
    except json.JSONDecodeError as e:
        return f"Error parsing JSON for document {doc_id}: {e}"
    
    lines = []
    
    # Document header
    lines.append("\n" + "=" * 80)
    lines.append(f"DOCUMENT ID: {doc_id}")
    lines.append("=" * 80)
    
    # Medications
    medications = data.get("medications", data.get("medication_entities", []))
    if medications:
        lines.append(print_section_header("MEDICATIONS", len(medications)))
        for med in medications:
            lines.append(format_entity(med))
    
    # Diseases
    diseases = data.get("diseases", data.get("disease_entities", []))
    if diseases:
        lines.append(print_section_header("DISEASES", len(diseases)))
        for disease in diseases:
            lines.append(format_entity(disease))
    
    # Genes/proteins
    genes = data.get("genes", data.get("genes_proteins", data.get("gene_protein_entities", [])))
    if genes:
        lines.append(print_section_header("GENES/PROTEINS", len(genes)))
        for gene in genes:
            lines.append(format_entity(gene))
    
    # Relationships
    drug_disease = data.get("drug_disease_relationships", [])
    if drug_disease:
        lines.append(print_section_header("DRUG-DISEASE RELATIONSHIPS", len(drug_disease)))
        for rel in drug_disease:
            lines.append(format_relationship(rel, "Drug-Disease"))
    
    drug_gene = data.get("drug_gene_relationships", [])
    if drug_gene:
        lines.append(print_section_header("DRUG-GENE RELATIONSHIPS", len(drug_gene)))
        for rel in drug_gene:
            lines.append(format_relationship(rel, "Drug-Gene"))
    
    gene_disease = data.get("gene_disease_relationships", [])
    if gene_disease:
        lines.append(print_section_header("GENE-DISEASE RELATIONSHIPS", len(gene_disease)))
        for rel in gene_disease:
            lines.append(format_relationship(rel, "Gene-Disease"))
            
    return "\n".join(lines)

if __name__ == "__main__":
    # Configure input and output files
    input_file = input("Enter path to PubTator data JSON file: ") or "./sample_pubtator_data.json"
    processed_file = "./processed_data.json"
    output_file = "./analysis_results.json"
    visualization_file = "./analysis_visualization.txt"
    
    # Process the documents
    processed_docs = process_documents(input_file, processed_file)
    
    # Set your OpenAI API key (you can also set it as an environment variable)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = input("Enter your OpenAI API key: ")
    
    # Analyze with OpenAI
    results = analyze_with_openai(processed_docs, api_key)
    
    # Save raw results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Analysis complete. Results saved to {output_file}")
    
    # Generate visualized results and save to file
    print("\n\nGenerating visualization of analysis results...")
    
    all_visualizations = []
    for doc in results:
        visualization = visualize_results(doc)
        all_visualizations.append(visualization)
        # Also print to console
        print(visualization)
    
    # Save visualized data to file
    with open(visualization_file, 'w') as f:
        f.write("\n".join(all_visualizations))
    
    print(f"\nVisualization saved to {visualization_file}")