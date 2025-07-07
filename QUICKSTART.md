# Quick Start Guide

This guide will help you get the biomedical knowledge graph system running quickly.

## Prerequisites Setup

### 1. Install MongoDB
```bash
# Ubuntu/Debian
sudo apt-get install mongodb

# Start MongoDB on custom port
mongod --port 28017 --dbpath /path/to/your/data
```

### 2. Install Neo4j
```bash
# Download Neo4j Community Edition
wget https://neo4j.com/artifact.php?name=neo4j-community-5.15.0-unix.tar.gz

# Extract and configure
tar -xf neo4j-community-5.15.0-unix.tar.gz
cd neo4j-community-5.15.0

# Edit conf/neo4j.conf to set port 7690
echo "server.bolt.listen_address=0.0.0.0:7690" >> conf/neo4j.conf

# Start Neo4j
bin/neo4j start

# Set password
bin/cypher-shell -a bolt://localhost:7690 -u neo4j -p neo4j
# Then run: ALTER USER neo4j SET PASSWORD '12345678';
```

### 3. Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key for later use

## Project Setup

### 1. Clone and Setup
```bash
# Clone your repository
git clone <your-repo-url>
cd thesis_kg

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate virtual environment
source thesis_env/bin/activate
```

### 2. Configure Environment
```bash
# Edit .env file
nano .env

# Add your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here
```

## Running the Pipeline

### Step 1: Parse PubTator Data
```bash
# Place your PubTator XML files in a directory
# Update the directory path in parsse.py if needed
python parsse.py
```

### Step 2: Filter Human Data
```bash
python humans.py
```

### Step 3: Extract Knowledge with AI
```bash
python new_data_extraction_from_gpt.py
# When prompted, enter the path to your PubTator JSON file
```

### Step 4: Update Knowledge Graph
```bash
python check_kg.py
# When prompted, enter the path to your analysis results
```

### Step 5: Launch Web Interface
```bash
streamlit run app.py
```

## Troubleshooting

### MongoDB Issues
```bash
# Check if MongoDB is running
sudo systemctl status mongodb

# Check port
netstat -tlnp | grep 28017
```

### Neo4j Issues
```bash
# Check Neo4j status
bin/neo4j status

# Check logs
tail -f logs/neo4j.log
```

### Python Dependencies
```bash
# If you get import errors
pip install --upgrade -r requirements.txt
```

## Sample Data Flow

1. **Input**: PubTator XML files with biomedical literature
2. **Processing**: AI extraction of entities and relationships
3. **Storage**: Neo4j knowledge graph with standardized schema
4. **Output**: Interactive web interface for exploration

## File Structure Overview

```
thesis_kg/
├── parsse.py           # XML → MongoDB
├── humans.py           # Filter human data
├── new_data_ext...py   # AI extraction
├── check_kg.py         # Update graph
├── app.py              # Web interface
└── thesis.ipynb       # Analysis notebook
```

Need help? Check the full README.md for detailed documentation.
