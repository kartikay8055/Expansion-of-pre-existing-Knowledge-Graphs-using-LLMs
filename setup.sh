#!/bin/bash

# Biomedical Knowledge Graph Setup Script
# This script helps set up the thesis environment

echo "🧬 Biomedical Knowledge Graph Setup"
echo "=================================="

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "Found: $python_version"

# Create virtual environment
echo "🐍 Creating virtual environment..."
python3 -m venv thesis_env
source thesis_env/bin/activate

# Install requirements
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data
mkdir -p graph_snapshots
mkdir -p outputs

# Check MongoDB connection
echo "🍃 Checking MongoDB connection..."
if command -v mongosh &> /dev/null; then
    echo "✅ MongoDB shell found"
    echo "Attempting to connect to MongoDB on port 28017..."
    mongosh --host localhost:28017 --eval "db.runCommand('ping')" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ MongoDB connection successful"
    else
        echo "❌ MongoDB connection failed"
        echo "💡 Make sure MongoDB is running on port 28017"
    fi
else
    echo "⚠️ MongoDB shell not found"
    echo "💡 Install MongoDB: https://www.mongodb.com/docs/manual/installation/"
fi

# Check Neo4j connection
echo "🔗 Checking Neo4j connection..."
if command -v cypher-shell &> /dev/null; then
    echo "✅ Neo4j cypher-shell found"
    echo "Attempting to connect to Neo4j on port 7690..."
    cypher-shell -a bolt://localhost:7690 -u neo4j -p 12345678 "RETURN 1" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Neo4j connection successful"
    else
        echo "❌ Neo4j connection failed"
        echo "💡 Make sure Neo4j is running on port 7690 with correct credentials"
    fi
else
    echo "⚠️ Neo4j cypher-shell not found"
    echo "💡 Install Neo4j: https://neo4j.com/docs/operations-manual/current/installation/"
fi

# Environment variables
echo "🔧 Setting up environment variables..."
if [ ! -f .env ]; then
    cat > .env << EOL
# MongoDB Configuration
MONGO_URI=mongodb://localhost:28017/
MONGO_DB=pubtator
MONGO_COLLECTION=PubTator3

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7690
NEO4J_USER=neo4j
NEO4J_PASSWORD=12345678
NEO4J_DATABASE=expansion

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Application Settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
EOL
    echo "✅ Created .env file"
    echo "🔑 Please update .env file with your OpenAI API key"
else
    echo "✅ .env file already exists"
fi

# Create sample configuration
echo "📄 Creating sample configuration files..."

# Create a sample config for the knowledge graph
cat > kg_config.json << EOL
{
    "entity_types": {
        "drug": "DRUG",
        "medication": "DRUG",
        "chemical": "DRUG",
        "disease": "DISEASE",
        "gene": "Gene",
        "protein": "PROTEIN",
        "gene_protein": "Gene"
    },
    "relationship_types": [
        "DRUG_DISEASE_ASSOCIATION",
        "DRUG_TARGET",
        "PROTEIN_DISEASE_ASSOCIATION",
        "DDI",
        "PPI",
        "DPI",
        "DRUG_PATHWAY_ASSOCIATION",
        "DISEASE_PATHWAY_ASSOCIATION",
        "PROTEIN_PATHWAY_ASSOCIATION"
    ],
    "processing_limits": {
        "max_documents_per_batch": 100,
        "max_entities_per_document": 1000,
        "max_relationships_per_document": 500
    }
}
EOL

echo "✅ Created kg_config.json"

# Display next steps
echo ""
echo "🎯 Setup Complete! Next Steps:"
echo "=============================="
echo "1. Activate the virtual environment:"
echo "   source thesis_env/bin/activate"
echo ""
echo "2. Update your .env file with the correct OpenAI API key"
echo ""
echo "3. Ensure MongoDB and Neo4j are running:"
echo "   - MongoDB on port 28017"
echo "   - Neo4j on port 7690"
echo ""
echo "4. Run the pipeline:"
echo "   python parsse.py          # Parse PubTator data"
echo "   python humans.py          # Filter human data"
echo "   python new_data_extraction_from_gpt.py  # Extract with AI"
echo "   python check_kg.py        # Update knowledge graph"
echo ""
echo "5. Start the web interface:"
echo "   streamlit run app.py"
echo ""
echo "📚 For more information, see README.md"
echo "🐛 Report issues at: https://github.com/kartikay8055/Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs"
