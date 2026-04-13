📁 Para aceitar arquivos no Assistente:
Bibliotecas já presentes no Process2Diagram:
Streamlit (streamlit) - Já instalada, suporta upload de arquivos nativamente
python-docx (python-docx) - Para processar arquivos .docx
PyPDF2 ou pdfplumber - Para extrair texto de PDFs
pandas - Para processar arquivos CSV/Excel
Código necessário:
import streamlit as st
from docx import Document
import PyPDF2
import pandas as pd
import io

# Upload de arquivo no Streamlit
uploaded_file = st.file_uploader(
    "Carregue um arquivo", 
    type=["txt", "docx", "pdf", "csv", "xlsx"]
)

if uploaded_file:
    # Detectar tipo de arquivo
    file_type = uploaded_file.name.split('.')[-1].lower()

    if file_type == "txt":
        text = uploaded_file.read().decode("utf-8")
    elif file_type == "docx":
        doc = Document(uploaded_file)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif file_type == "pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = "\n".join([page.extract_text() for page in pdf_reader.pages])
    elif file_type == "csv":
        df = pd.read_csv(uploaded_file)
        text = df.to_string()
    elif file_type == "xlsx":
        df = pd.read_excel(uploaded_file)
        text = df.to_string()

📊 Para gerar gráficos no Assistente:
Bibliotecas recomendadas:
Plotly (plotly) - Gráficos interativos (recomendado)
Matplotlib (matplotlib) - Gráficos estáticos
Altair (altair) - Declarativo e integrado com Streamlit
Seaborn (seaborn) - Estatística e visualização
Instalação:
pip install plotly matplotlib altair seaborn

Exemplos de uso:
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# 1. Gráfico de barras com Plotly
def plot_bar_chart(data):
    fig = px.bar(data, x='categoria', y='valor', title='Distribuição por Categoria')
    st.plotly_chart(fig)

# 2. Gráfico de pizza
def plot_pie_chart(data):
    fig = px.pie(data, values='valor', names='categoria', title='Composição')
    st.plotly_chart(fig)

# 3. Linha do tempo
def plot_timeline(dates, values):
    fig = go.Figure(data=go.Scatter(x=dates, y=values, mode='lines+markers'))
    fig.update_layout(title='Evolução ao longo do tempo')
    st.plotly_chart(fig)

# 4. Heatmap com Seaborn
def plot_heatmap(matrix):
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(matrix, annot=True, fmt='.2f', cmap='coolwarm', ax=ax)
    st.pyplot(fig)

📦 Pacotes Python completos para instalar:
# Para upload de arquivos
pip install python-docx PyPDF2 pandas openpyxl xlrd

# Para gráficos
pip install plotly matplotlib seaborn altair

# Para análise de dados (opcional)
pip install numpy scipy scikit-learn

🎯 Integração com o Assistente existente:
Na página pages/Assistente.py:
import streamlit as st

# Adicionar seção de upload
with st.sidebar.expander("📁 Upload de Arquivos"):
    uploaded_file = st.file_uploader(
        "Carregue dados para análise",
        type=["txt", "docx", "pdf", "csv", "xlsx", "json"]
    )

    if uploaded_file:
        # Processar arquivo
        data = process_uploaded_file(uploaded_file)
        st.session_state['uploaded_data'] = data
        st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")

# Adicionar seção de visualização
if 'uploaded_data' in st.session_state:
    with st.expander("📊 Visualização de Dados"):
        # Mostrar dados
        st.dataframe(st.session_state['uploaded_data'])

        # Opções de gráficos
        chart_type = st.selectbox(
            "Tipo de gráfico",
            ["Barras", "Pizza", "Linha", "Heatmap", "Dispersão"]
        )

        if chart_type == "Barras":
            plot_bar_chart(st.session_state['uploaded_data'])

🔧 Configuração do requirements.txt atualizado:
# Processamento de arquivos
python-docx>=0.8.11
PyPDF2>=3.0.0
pandas>=2.0.0
openpyxl>=3.1.0
xlrd>=2.0.0

# Visualização de dados
plotly>=5.18.0
matplotlib>=3.7.0
seaborn>=0.12.0
altair>=5.0.0

# Streamlit e base
streamlit>=1.28.0
streamlit-option-menu>=0.3.6

# Análise de texto (já existentes)
spacy>=3.7.0
nltk>=3.8.0

💡 Casos de uso específicos para o SDEA:
Upload de relatórios de auditoria (PDF/DOCX) para análise automática
Gráficos de métricas do projeto (requisitos por tipo, status, prioridade)
Visualização de progresso das reuniões ao longo do tempo
Análise de participantes e frequência nas reuniões
Dashboard de requisitos com filtros interativos
Você já tem a infraestrutura básica com Streamlit. Essas adições permitirão que o Assistente se torne uma ferramenta mais completa para análise e visualização de dados do projeto SDEA.
