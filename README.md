# Process2Diagram

Prototype application that converts **meeting transcripts into process diagrams**.

The application receives a **natural language transcription**, extracts a **structured process**, and generates:

* a **Mermaid flowchart**
* a **Draw.io (.drawio XML) diagram**
* a **structured JSON representation of the process**

The goal is to demonstrate how **process documentation can be automatically generated from conversations**.

---

# Overview

Many business processes are defined during meetings but never formally documented.

This project explores a pipeline that transforms **spoken descriptions of processes** into **visual diagrams automatically**.

Pipeline:

```
Meeting Transcript
       │
       ▼
Text Preprocessing
       │
       ▼
Process Extraction
(heuristic or LLM-based)
       │
       ▼
Structured Process Model
       │
       ├── JSON representation
       ├── Mermaid diagram
       └── Draw.io diagram
```

---

# Example

Input transcript:

```
1) The NDOC team uploads the photo.
2) The system detects faces using RetinaFace.
3) The specialist identifies the people.
4) The system generates the SVG legend.
5) The files are uploaded to the ECM.
```

Generated diagram:

```
Upload Photo
      │
      ▼
Face Detection
      │
      ▼
Identify People
      │
      ▼
Generate SVG Legend
      │
      ▼
Upload to ECM
```

---

# Architecture

The project is intentionally **modular**.

The Streamlit application only orchestrates the pipeline.

```
process2diagram
│
├── app.py
│
├── modules
│   ├── config.py
│   ├── ingest.py
│   ├── preprocess.py
│   ├── schema.py
│   ├── extract_heuristic.py
│   ├── extract_llm.py
│   ├── diagram_mermaid.py
│   ├── diagram_drawio.py
│   └── utils.py
│
└── requirements.txt
```

### app.py

Streamlit interface and orchestration layer.

### ingest.py

Handles transcript ingestion.

### preprocess.py

Text normalization and filler word removal.

### schema.py

Defines the internal **process model**.

### extract_heuristic.py

Extracts process steps using rule-based heuristics.

### extract_llm.py

Placeholder for LLM-based extraction.

### diagram_mermaid.py

Generates Mermaid flowcharts.

### diagram_drawio.py

Generates Draw.io XML diagrams.

### utils.py

Utility functions such as JSON export.

---

# Process Model

The system converts the transcript into a structured representation.

```
Process
 ├── Steps
 │    ├── id
 │    ├── title
 │    ├── description
 │    └── actor
 │
 └── Edges
      ├── source
      └── target
```

Example JSON:

```json
{
  "name": "Photo Processing",
  "steps": [
    {"id": "S01", "title": "Upload Photo"},
    {"id": "S02", "title": "Detect Faces"},
    {"id": "S03", "title": "Identify People"}
  ],
  "edges": [
    {"source": "S01", "target": "S02"},
    {"source": "S02", "target": "S03"}
  ]
}
```

---

# Installation

Clone the repository:

```
git clone https://github.com/your-user/process2diagram.git
cd process2diagram
```

Install dependencies:

```
pip install -r requirements.txt
```

---

# Running the Application

Run Streamlit:

```
streamlit run app.py
```

The application will open in the browser.

---

# Using the Application

1. Paste a meeting transcript.
2. Click **Generate Diagram**.
3. The system will:

   * preprocess the text
   * extract process steps
   * generate diagrams.

Outputs available:

* Mermaid diagram preview
* Mermaid code
* structured JSON
* downloadable `.drawio` file

---

# Deploying on Streamlit Cloud

1. Push the repository to GitHub
2. Go to **Streamlit Cloud**
3. Create a new app
4. Select the repository
5. Set:

```
Main file: app.py
```

Streamlit Cloud will install dependencies from:

```
requirements.txt
```

---

# Limitations

This PoC uses a **heuristic extractor**.

Therefore:

* extraction accuracy depends on transcript structure
* numbered steps or bullet lists improve results
* complex branching logic is not yet supported

---

# Future Improvements

Possible extensions include:

### LLM-based process extraction

Use an LLM to convert transcripts into structured processes.

```
Transcript
   │
   ▼
LLM
   │
   ▼
Process JSON
```

### BPMN generation

Support BPMN diagrams.

### Actor lanes (Swimlanes)

Detect actors and generate swimlane diagrams.

### Meeting audio pipeline

```
Audio Recording
      │
      ▼
Speech-to-text
      │
      ▼
Process extraction
      │
      ▼
Diagram generation
```

---

# Potential Use Cases

Business process documentation

Operational workflows

Meeting knowledge capture

Process mining support

Architecture documentation

---

# Related Tools

Draw.io (Diagrams.net)

Mermaid

Graphviz

PlantUML

---

# License

MIT License.

2️⃣ **Um exemplo real de transcrição → diagrama**
3️⃣ **Uma versão mais sofisticada do pipeline usando LLM** (que melhora muito a qualidade da extração).
