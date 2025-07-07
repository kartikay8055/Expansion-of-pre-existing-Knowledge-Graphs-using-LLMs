# Biomedical Knowledge Graph Construction and Enhancement

A comprehensive thesis project for constructing and enhancing biomedical knowledge graphs using PubTator data, OpenAI analysis, and Neo4j graph database technology.

## 🎯 Project Overview

This project implements a complete pipeline for:
- Parsing biomedical literature data from PubTator
- Extracting entities and relationships using AI
- Building and visualizing knowledge graphs
- Interactive web-based exploration of biomedical relationships

## 🏗️ System Architecture

```
PubTator XML → MongoDB → Entity Extraction → Knowledge Graph → Web Interface
     ↓              ↓            ↓                ↓              ↓
  parsse.py    humans.py   new_data_ext...   check_kg.py    app.py
```

## 📁 Project Structure

```
thesis_kg/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── parsse.py                          # PubTator XML parser
├── humans.py                          # Human-specific data filter
├── extract_from_dump.py               # Node extraction from Neo4j
├── node_reln_fromdump.py              # Relationship type extraction
├── new_data_extraction_from_gpt.py    # AI-powered entity extraction
├── check_kg.py                        # Knowledge graph updater
├── app.py                             # Streamlit web interface
└── thesis.ipynb                       # Jupyter notebook for analysis
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- MongoDB (localhost:28017)
- Neo4j (localhost:7690)
- OpenAI API key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kartikay8055/Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs.git
   cd Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export MONGO_URI="mongodb://localhost:28017/"
   ```

4. **Start required services:**
   ```bash
   # Start MongoDB
   mongod --port 28017
   
   # Start Neo4j
   neo4j start
   ```

## 📊 Pipeline Workflow

### 1. Data Parsing (`parsse.py`)
**Purpose**: Parse PubTator XML files and store in MongoDB

```bash
python parsse.py
```

**Features**:
- Parses biomedical literature XML from PubTator
- Extracts entities, annotations, and relationships
- Stores structured data in MongoDB with proper indexing
- Handles large-scale data processing with batch operations

### 2. Human Data Filtering (`humans.py`)
**Purpose**: Filter dataset to human-specific biomedical data

```bash
python humans.py
```

**Features**:
- Identifies human-related documents (species ID: 9606)
- Removes non-human species data
- Optimizes dataset for human biomedical research

### 3. Knowledge Graph Analysis (`extract_from_dump.py` & `node_reln_fromdump.py`)
**Purpose**: Extract existing graph structure for analysis

```bash
python extract_from_dump.py
python node_reln_fromdump.py
```

**Features**:
- Exports existing Neo4j nodes and relationships
- Generates relation type mappings
- Creates baseline for knowledge graph expansion

### 4. AI-Powered Entity Extraction (`new_data_extraction_from_gpt.py`)
**Purpose**: Extract biomedical entities and relationships using OpenAI

```bash
python new_data_extraction_from_gpt.py
```

**Features**:
- Processes PubTator documents with GPT-4
- Extracts drugs, diseases, genes, and proteins
- Identifies standardized biomedical relationships
- Maps to existing knowledge graph schema

**Supported Relationship Types**:
- `DRUG_DISEASE_ASSOCIATION`
- `DRUG_TARGET`
- `PROTEIN_DISEASE_ASSOCIATION`
- `DDI` (Drug-Drug Interaction)
- `PPI` (Protein-Protein Interaction)
- `DPI` (Drug-Protein Interaction)
- And 10+ more standardized types

### 5. Knowledge Graph Updates (`check_kg.py`)
**Purpose**: Update Neo4j knowledge graph with extracted data

```bash
python check_kg.py
```

**Features**:
- Validates and standardizes entity names
- Prevents duplicate entities and relationships
- Comprehensive update tracking and reporting
- Maintains data provenance and sources

### 6. Interactive Visualization (`app.py`)
**Purpose**: Web-based knowledge graph exploration

```bash
streamlit run app.py
```

**Features**:
- Interactive graph visualization with Plotly
- Node and relationship filtering
- Neighborhood exploration
- Graph snapshots and comparisons
- Statistical analysis dashboard

## 🔧 Configuration

### MongoDB Settings
- **Host**: localhost
- **Port**: 28017
- **Database**: pubtator
- **Collection**: PubTator3

### Neo4j Settings
- **Host**: localhost
- **Port**: 7690
- **Database**: expansion
- **Username**: ********
- **Password**: ********

### OpenAI Configuration
- **Model**: gpt-4o-mini
- **Temperature**: 0.1
- **Max Tokens**: 1500

## 📈 Features

### Entity Management
- **Automatic Deduplication**: Prevents duplicate entities using case-insensitive matching
- **Multi-source Integration**: Combines data from PubTator and AI extraction
- **Standardized Identifiers**: Maps various ID formats to standard databases

### Relationship Validation
- **Type Standardization**: Maps relationships to knowledge graph schema
- **Bidirectional Checking**: Prevents duplicate relationships in both directions
- **Confidence Scoring**: Maintains relationship confidence metrics

### Visualization & Analysis
- **Interactive Web Interface**: Real-time graph exploration
- **Statistical Dashboard**: Entity and relationship analytics
- **Export Capabilities**: Graph data export in multiple formats
- **Snapshot Management**: Version control for graph states

## 🛠️ Development

### Adding New Entity Types
1. Update label mapping in `check_kg.py`
2. Add extraction logic in `new_data_extraction_from_gpt.py`
3. Update visualization in `app.py`

### Adding New Relationship Types
1. Add to `EXISTING_RELATION_TYPES` list
2. Update relationship mapping dictionaries
3. Add visualization support

## 📚 Research Applications

- **Drug Discovery**: Identify potential drug-target interactions
- **Disease Mechanism**: Understand gene-disease associations
- **Literature Mining**: Extract knowledge from biomedical texts
- **Hypothesis Generation**: Discover novel biomedical relationships

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **PubTator**: For providing biomedical literature annotations
- **Neo4j**: Graph database technology
- **OpenAI**: AI-powered entity extraction
- **Streamlit**: Web interface framework

## 📞 Contact

- **Author**: Kartikay
- **GitHub**: [@kartikay8055](https://github.com/kartikay8055)
- **Repository**: [Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs](https://github.com/kartikay8055/Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs)

## 🔍 Citation

If you use this work in your research, please cite:

```bibtex
@thesis{kartikay2025biokg,
  title={Expansion of pre-existing Knowledge Graphs using LLMs},
  author={Kartikay},
  year={2025},
  url={https://github.com/kartikay8055/Expansion-of-pre-existing-Knowledge-Graphs-using-LLMs},
}
```

---

**Last Updated**: July 2025
