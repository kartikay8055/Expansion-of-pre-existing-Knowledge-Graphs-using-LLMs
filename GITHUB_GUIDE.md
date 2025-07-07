# GitHub Upload Guide

This guide walks you through uploading your thesis project to GitHub.

## Step 1: Prepare Your Repository

### Clean Up Sensitive Data
Before uploading, make sure to remove any sensitive information:

```bash
# Remove any API keys from files
grep -r "sk-" . --exclude-dir=.git
grep -r "api_key" . --exclude-dir=.git

# Check for hardcoded passwords
grep -r "12345678" . --exclude-dir=.git

# Remove large data files (they're already in .gitignore)
rm -f *.xml *.json.gz data/*
```

### Verify .gitignore
Make sure your `.gitignore` file excludes:
- API keys and credentials
- Large data files
- Database dumps
- Log files
- Environment-specific files

## Step 2: Initialize Git Repository

```bash
# Navigate to your project directory
cd /home/kartikay23230/thesis_kg

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Biomedical Knowledge Graph thesis project

- Complete pipeline for PubTator data processing
- AI-powered entity and relationship extraction
- Neo4j knowledge graph construction
- Interactive web interface with Streamlit
- Comprehensive documentation and setup scripts"
```

## Step 3: Create GitHub Repository

### Option A: Using GitHub CLI (if installed)
```bash
# Install GitHub CLI if not available
# Ubuntu: sudo apt install gh
# Mac: brew install gh

# Login to GitHub
gh auth login

# Create repository
gh repo create thesis_kg --public --description "Biomedical Knowledge Graph Construction and Enhancement"

# Push code
git remote add origin https://github.com/YOUR_USERNAME/thesis_kg.git
git branch -M main
git push -u origin main
```

### Option B: Using GitHub Web Interface

1. **Go to GitHub.com**
   - Sign in to your account
   - Click the "+" icon → "New repository"

2. **Configure Repository**
   - Repository name: `thesis_kg`
   - Description: `Biomedical Knowledge Graph Construction and Enhancement`
   - Set to Public (recommended for thesis work)
   - Don't initialize with README (we already have one)

3. **Connect Local Repository**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/thesis_kg.git
   git branch -M main
   git push -u origin main
   ```

## Step 4: Configure Repository Settings

### Add Repository Topics
In your GitHub repository:
1. Go to Settings → General
2. Add topics: `bioinformatics`, `knowledge-graph`, `neo4j`, `openai`, `thesis`, `biomedical`, `nlp`

### Enable GitHub Pages (Optional)
If you want to host documentation:
1. Go to Settings → Pages
2. Source: Deploy from a branch
3. Branch: main, folder: / (root)

### Set Up Issues and Discussions
1. Go to Settings → General
2. Enable Issues and Discussions for collaboration

## Step 5: Create Release

### Tag Your Version
```bash
# Create and push a version tag
git tag -a v1.0.0 -m "Version 1.0.0: Complete thesis implementation"
git push origin v1.0.0
```

### Create GitHub Release
1. Go to your repository → Releases
2. Click "Create a new release"
3. Tag: v1.0.0
4. Title: "Biomedical Knowledge Graph v1.0.0"
5. Description:
   ```markdown
   ## Features
   - Complete PubTator data processing pipeline
   - AI-powered biomedical entity extraction using OpenAI GPT-4
   - Neo4j knowledge graph construction with 16+ relationship types
   - Interactive Streamlit web interface for graph exploration
   - Comprehensive documentation and setup automation
   
   ## What's Included
   - Source code for all pipeline components
   - Jupyter notebook for data analysis
   - Setup scripts and configuration files
   - Comprehensive README and documentation
   
   ## Requirements
   - Python 3.8+
   - MongoDB
   - Neo4j
   - OpenAI API key
   ```

## Step 6: Repository Structure Check

Your final repository should look like:

```
thesis_kg/
├── README.md                    ✅ Main documentation
├── QUICKSTART.md               ✅ Quick setup guide
├── LICENSE                     ✅ MIT License
├── requirements.txt            ✅ Python dependencies
├── .gitignore                  ✅ Ignore sensitive files
├── setup.sh                    ✅ Automated setup
├── .env.example               ⚠️ Need to create
├── parsse.py                   ✅ PubTator parser
├── humans.py                   ✅ Human data filter
├── extract_from_dump.py        ✅ Graph extraction
├── node_reln_fromdump.py       ✅ Relation extraction
├── new_data_extraction_from_gpt.py ✅ AI extraction
├── check_kg.py                 ✅ Graph updater
├── app.py                      ✅ Web interface
├── thesis.ipynb               ✅ Analysis notebook
└── kg_config.json             ✅ Configuration
```

## Step 7: Create Environment Template

Create `.env.example` for users:

```bash
# Create template environment file
cat > .env.example << 'EOL'
# MongoDB Configuration
MONGO_URI=mongodb://localhost:28017/
MONGO_DB=pubtator
MONGO_COLLECTION=PubTator3

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7690
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_DATABASE=expansion

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Application Settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
EOL

# Add and commit
git add .env.example
git commit -m "Add environment template file"
git push
```

## Step 8: Final Verification

### Test Clone Process
```bash
# In a different directory, test the setup
cd /tmp
git clone https://github.com/YOUR_USERNAME/thesis_kg.git
cd thesis_kg
./setup.sh
```

### Check Repository Health
- ✅ All files uploaded successfully
- ✅ README displays correctly
- ✅ No sensitive data exposed
- ✅ Setup script works
- ✅ Requirements file is complete

## Best Practices for Academic Repositories

### 1. Professional README
- Clear project description
- Installation instructions
- Usage examples
- Citation information

### 2. Proper Documentation
- Code comments
- Docstrings for functions
- Architecture diagrams
- API documentation

### 3. Version Control
- Meaningful commit messages
- Tagged releases
- Change logs

### 4. Reproducibility
- Fixed dependency versions
- Setup automation
- Sample data/configs
- Clear instructions

## Sharing Your Work

### Academic Sharing
```markdown
Repository URL: https://github.com/YOUR_USERNAME/thesis_kg
Citation: Available in README.md
License: MIT (allows academic and commercial use)
```

### Social Media
```
🧬 Just published my thesis code on GitHub! 

Biomedical Knowledge Graph Construction using:
🤖 AI-powered entity extraction
📊 Neo4j graph database
🔬 PubTator biomedical data
💻 Interactive web interface

Check it out: https://github.com/YOUR_USERNAME/thesis_kg

#bioinformatics #AI #knowledgegraph #thesis
```

Your repository is now ready for academic and professional sharing! 🎉
