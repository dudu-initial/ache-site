# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import re # Importando a biblioteca de expressões regulares

st.set_page_config(
    page_title="Gerador de Cronograma - Embalagens",
    page_icon="logotipoache.png",
    layout="wide")

# --- INÍCIO: INICIALIZAÇÃO DO SESSION STATE ---
# Essencial para que o chatbot possa se comunicar com os filtros da sidebar
if 'chatbot_filters' not in st.session_state:
    st.session_state.chatbot_filters = {'categoria': None, 'fase_condicoes': {}}
# --- FIM: INICIALIZAÇÃO DO SESSION STATE ---


st.title("Gerador automático de cronogramas — Embalagens")
st.markdown(
    """
    Faça upload do Excel com as tarefas (colunas esperadas: Número, Classificação, Categoria, Fase, Condição, Nome, Duração ...)
    - Tarefas com **Condição = 'Sempre'** serão sempre incluídas.
    - Você pode escolher A/B/C por fase.
    - O modo padrão agenda **cada fase iniciando somente após a fase anterior terminar** (dependência automática entre fases).
    """
)



# --- INÍCIO: LÓGICA DO CHATBOT ---
def parse_command(text, all_categorias, all_fases, all_condicoes):
    """Interpreta o texto do usuário para extrair filtros."""
    text_lower = text.lower()
    parsed = {'categoria': None, 'fase_condicoes': {}}

    # 1. Encontrar a Categoria
    for cat in all_categorias:
        if cat.lower() in text_lower:
            parsed['categoria'] = cat
            break # Pega a primeira que encontrar

    # 2. Encontrar a Fase
    target_fase = None
    for fase in all_fases:
        if fase.lower() in text_lower:
            target_fase = fase
            break # Pega a primeira que encontrar

    # 3. Encontrar as Condições (e associar com a fase encontrada, se houver)
    found_condicoes = []
    for cond in all_condicoes:
        # Usamos expressões regulares para encontrar a condição como uma palavra isolada
        # Ex: encontrar 'A' mas não o 'a' em 'fase'
        if re.search(r'\b' + re.escape(cond.lower()) + r'\b', text_lower):
            found_condicoes.append(cond)

    if target_fase and found_condicoes:
        # Associa as condições à fase específica encontrada
        parsed['fase_condicoes'][target_fase] = found_condicoes
    # Se condições foram encontradas, mas NENHUMA fase foi especificada...
    elif not target_fase and found_condicoes:
        # ...então aplicamos essas condições a TODAS as fases disponíveis.
        st.info(f"Condições {found_condicoes} aplicadas a todas as fases por padrão, pois nenhuma fase foi especificada.")
        for fase in all_fases:
            parsed['fase_condicoes'][fase] = found_condicoes

    return parsed

# --- FIM: LÓGICA DO CHATBOT ---


# ---------- Helpers para detectar colunas ----------
def find_col(df, keywords):
    """Encontra a primeira coluna cujo nome contenha qualquer uma das keywords (case-insensitive)."""
    cols = df.columns.tolist()
    lower = [c.lower() for c in cols]
    for kw in keywords:
        for i, c in enumerate(lower):
            if kw.lower() in c:
                return cols[i]
    return None

def normalize_df_columns(df):
    # tenta detectar colunas principais e renomear para nomes simples em PT
    mapping = {}
    if find_col(df, ['num', 'número', 'numero', 'id']):
        mapping[find_col(df, ['num', 'número', 'numero', 'id'])] = 'numero'
    if find_col(df, ['classif', 'classificação', 'classificacao']):
        mapping[find_col(df, ['classif', 'classificação', 'classificacao'])] = 'classificacao'
    if find_col(df, ['categ', 'categoria']):
        mapping[find_col(df, ['categ', 'categoria'])] = 'categoria'
    if find_col(df, ['fase']):
        mapping[find_col(df, ['fase'])] = 'fase'
    if find_col(df, ['condi', 'condição', 'condicao']):
        mapping[find_col(df, ['condi', 'condição', 'condicao'])] = 'condicao'
    if find_col(df, ['nome', 'tarefa', 'atividade']):
        mapping[find_col(df, ['nome', 'tarefa', 'atividade'])] = 'nome'
    if find_col(df, ['dur', 'duração', 'duracao', 'days']):
        mapping[find_col(df, ['dur', 'duração', 'duracao', 'days'])] = 'duracao'
    # colunas opcionais
    if find_col(df, ['como fazer', 'comofazer', 'como_fazer']):
        mapping[find_col(df, ['como fazer', 'comofazer', 'como_fazer'])] = 'como_fazer'
    if find_col(df, ['doc', 'documento']):
        mapping[find_col(df, ['doc', 'documento'])] = 'documento_referencia'

    df = df.rename(columns=mapping)
    return df

# ---------- Ler arquivo ----------
uploaded = st.file_uploader("Upload do arquivo .xlsx (ou .csv) com as tarefas", type=['xlsx', 'xls', 'csv'])
if uploaded:
    try:
        if uploaded.name.lower().endswith('.csv'):
            # tenta detectar separador comum, mas por segurança usa sep=";"
            try:
                df_raw = pd.read_csv(uploaded, sep=";")
            except:
                df_raw = pd.read_csv(uploaded)
        else:
            df_raw = pd.read_excel(uploaded, engine='openpyxl')
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        st.stop()
else:
    st.info("Nenhum arquivo carregado ainda — usando um exemplo pequeno para demonstração.")
    # exemplo mínimo
    sample = {
        'Número': [1,2,3,4,5,6],
        'Classificação': ['Embalagem Primária']*6,
        'Categoria': ['Ampolas', 'Seringas', 'Ampolas', 'Seringas', 'Ampolas', 'Seringas'],
        'Fase': ['1. Escopo & Briefing','1. Escopo & Briefing','2. Desenvolvimento','2. Desenvolvimento','3. Validação','3. Validação'],
        'Condição': ['Sempre','A','B','Sempre','C','B'],
        'Nome': ['Definir requisitos','Estabelecer volume','Levant. normas','Definir shelf life','Identificar processo','Planejar prazos'],
        'Duração': [5,10,5,5,7,3],
        'Como Fazer': ['Texto.1','Texto.2','Texto.3','Texto.4','Texto.5','Texto.6']
    }
    df_raw = pd.DataFrame(sample)

df = normalize_df_columns(df_raw.copy())

# Garante colunas mínimas
required = ['numero','fase','condicao','nome','duracao']
missing = [c for c in required if c not in df.columns]
if missing:
    st.warning(f"O arquivo não tem todas as colunas esperadas. Colunas faltando (esperadas): {missing}. Tente mapear manualmente ou renomear no arquivo.")
    st.write("Colunas detectadas no arquivo:", df_raw.columns.tolist())

# normaliza duracao
if 'duracao' in df.columns:
    try:
        df['duracao'] = df['duracao'].astype(str).str.extract('(\\d+)').astype(float)
    except:
        df['duracao'] = pd.to_numeric(df['duracao'], errors='coerce')
    df['duracao'] = pd.to_numeric(df['duracao'], errors='coerce').fillna(1.0)
else:
    st.error("Coluna de duração não encontrada — não é possível continuar.")
    st.write("Colunas detectadas no arquivo:", df_raw.columns.tolist())
    st.write("Colunas após normalização:", df.columns.tolist())
    st.stop()

df['condicao'] = df['condicao'].astype(str).str.strip()


# --- INÍCIO: INTERFACE DO CHATBOT ---
st.subheader("🤖 Use linguagem natural para filtrar (opcional)")
user_command = st.text_input(
    "Digite um comando para pré-selecionar os filtros:",
    placeholder="Ex: cronograma para Ampolas com condições A e C na fase de Desenvolvimento"
)

if st.button("Aplicar Comando"):
    # Extrai todas as opções possíveis do dataframe atual
    all_cats = df['categoria'].dropna().unique().tolist() if 'categoria' in df.columns else []
    all_phases = df['fase'].dropna().unique().tolist()
    all_conds = [c for c in df['condicao'].dropna().unique() if c.lower() != 'sempre']
    # Chama a função de parsing e salva no session_state
    st.session_state.chatbot_filters = parse_command(user_command, all_cats, all_phases, all_conds)
# --- FIM: INTERFACE DO CHATBOT ---

st.sidebar.image("logotipoache.png", use_container_width=True)
# ---------- Filtros básicos ----------
st.sidebar.header("Filtros do projeto")
start_date = st.sidebar.date_input("Data de início do projeto", value=pd.Timestamp.today().date())

# Usa o valor do chatbot para definir o padrão da categoria
categoria_options = ['Todos'] + sorted(df['categoria'].dropna().unique().tolist()) if 'categoria' in df.columns else ['Todos']
default_cat_index = 0
if st.session_state.chatbot_filters.get('categoria') in categoria_options:
    default_cat_index = categoria_options.index(st.session_state.chatbot_filters['categoria'])

selected_categoria = st.sidebar.selectbox(
    "Categoria do projeto (filtrar)",
    categoria_options,
    index=default_cat_index
)

if selected_categoria != 'Todos' and 'categoria' in df.columns:
    df = df[df['categoria'] == selected_categoria]

phases = list(df['fase'].dropna().unique())
phases_ordered = phases
st.sidebar.markdown(f"**Fases detectadas:** {len(phases_ordered)}")



st.sidebar.subheader("Condições por fase (Sempre é sempre incluída)")
phase_conditions = {}
possible_conditions = sorted(list(df['condicao'].dropna().unique()))
option_conditions = [c for c in possible_conditions if c.lower() != 'sempre']
if not option_conditions:
    option_conditions = ['A','B','C']

for ph in phases_ordered:
    # --- INÍCIO DA CORREÇÃO ---
    # 1. Pega os valores padrão sugeridos pelo chatbot (ou todos, se não houver sugestão).
    suggested_defaults = st.session_state.chatbot_filters.get('fase_condicoes', {}).get(ph, option_conditions)

    # 2. Valida os valores, garantindo que apenas os que existem nas opções atuais sejam usados.
    final_default = [cond for cond in suggested_defaults if cond in option_conditions]
    # --- FIM DA CORREÇÃO ---

    sel = st.sidebar.multiselect(
        f"{ph}",
        options=option_conditions,
        default=final_default, # Usa a lista de padrões validada e segura
        key=f"cond_{ph}"
    )
    if 'Sempre' in possible_conditions or 'sempre' in [x.lower() for x in possible_conditions]:
        sel = list(set(sel + ['Sempre']))
    phase_conditions[ph] = sel

st.sidebar.markdown("### Modo de agendamento")
phase_sequential = st.sidebar.checkbox(
    "Agendar fases sequencialmente (cada fase começa após a anterior terminar) — RECOMENDADO",
    value=True
)
chain_seq = st.sidebar.checkbox("Encadear tarefas sequencialmente (uma continua após a outra)", value=False)
st.sidebar.markdown("Se 'Encadear tarefas' for ativo: todas as tarefas selecionadas seguem em sequência única (ignora fase->fase).")

# ... (O RESTO DO CÓDIGO PERMANECE O MESMO) ...
# ---------- Montar lista de tarefas de saída ----------
selected_rows = []
for ph in phases_ordered:
    conds = phase_conditions.get(ph, [])
    conds_norm = [c.lower() for c in conds]
    df_ph = df[df['fase'] == ph].copy()
    mask = df_ph['condicao'].astype(str).str.lower().isin(conds_norm) | (df_ph['condicao'].astype(str).str.lower() == 'sempre')
    df_ph = df_ph[mask]
    selected_rows.append(df_ph)

if selected_rows:
    df_sel = pd.concat(selected_rows, ignore_index=True)
else:
    df_sel = df.iloc[0:0].copy()

if 'numero' in df_sel.columns:
    phase_order_map = {ph: i for i, ph in enumerate(phases_ordered)}
    df_sel['phase_order'] = df_sel['fase'].map(phase_order_map)
    df_sel = df_sel.sort_values(by=['phase_order', 'numero']).reset_index(drop=True)
    df_sel = df_sel.drop(columns=['phase_order'])
else:
    df_sel = df_sel.reset_index(drop=True)

st.header("Resumo das tarefas selecionadas")
st.write(f"Tarefas selecionadas: {len(df_sel)}")
st.dataframe(df_sel[['numero','fase','condicao','nome','duracao']].fillna('') if 'numero' in df_sel.columns else df_sel[['fase','condicao','nome','duracao']].fillna(''))

# ---------- Calcular datas (modo fase->fase) ----------
project_start = pd.to_datetime(start_date)
df_sel['start'] = pd.NaT
df_sel['end'] = pd.NaT

if len(df_sel) > 0:
    if chain_seq:
        durations = df_sel['duracao'].astype(float).fillna(1)
        start_offsets = durations.cumsum() - durations
        df_sel['start'] = project_start + pd.to_timedelta(start_offsets, unit='D')
        df_sel['end'] = df_sel['start'] + pd.to_timedelta(durations, unit='D')
    elif phase_sequential:
        current_phase_start = project_start
        for ph in phases_ordered:
            df_ph_idx = df_sel[df_sel['fase'] == ph].index.tolist()
            if not df_ph_idx:
                continue
            ends = []
            for idx in df_ph_idx:
                dur = float(df_sel.at[idx, 'duracao'])
                start_task = current_phase_start
                end_task = start_task + pd.to_timedelta(dur, unit='D')
                df_sel.at[idx, 'start'] = start_task
                df_sel.at[idx, 'end'] = end_task
                ends.append(end_task)
            current_phase_start = max(ends) if ends else current_phase_start
    else:
        for ph in phases_ordered:
            df_ph = df_sel[df_sel['fase'] == ph].copy()
            if df_ph.empty:
                continue
            durations = df_ph['duracao'].astype(float).fillna(1)
            start_offsets = durations.cumsum() - durations
            starts_ph = project_start + pd.to_timedelta(start_offsets, unit='D')
            ends_ph = starts_ph + pd.to_timedelta(durations, unit='D')
            df_sel.loc[df_ph.index, 'start'] = starts_ph
            df_sel.loc[df_ph.index, 'end'] = ends_ph

df_sel['start'] = pd.to_datetime(df_sel['start'])
df_sel['end'] = pd.to_datetime(df_sel['end'])

# ---------- Visualização Gantt (Plotly) ----------
st.header("Cronograma (Gantt)")
if df_sel.empty:
    st.info("Nenhuma tarefa selecionada para gerar cronograma.")
else:
    df_plot = df_sel.sort_values('start').copy()
    if 'numero' in df_plot.columns:
        df_plot['task_label'] = df_plot['fase'].astype(str) + ' - ' + df_plot['numero'].astype(str) + ' - ' + df_plot['nome'].astype(str)
    else:
        df_plot['task_label'] = df_plot['fase'].astype(str) + ' - ' + df_plot['nome'].astype(str)

    fig = px.timeline(
        df_plot,
        x_start="start",
        x_end="end",
        y="fase",
        color="condicao" if 'condicao' in df_plot.columns else None,
        hover_data=['task_label','duracao']
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    total_days = (df_sel['end'].max() - df_sel['start'].min()).days if not df_sel.empty and df_sel['start'].min() is not pd.NaT else 0
    st.write(f"Duração total do cronograma (dias, intervalo entre 1ª e última tarefa): **{total_days}** dias")

# ---------- Download / Export ----------
st.header("Exportar cronograma")
if not df_sel.empty:
    csv = df_sel.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar CSV", data=csv, file_name="cronograma.csv", mime="text/csv")
    towrite = BytesIO()
    with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
        df_sel.to_excel(writer, index=False, sheet_name='cronograma')

    towrite.seek(0)
    st.download_button("📥 Baixar XLSX", data=towrite, file_name="cronograma.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Nenhum cronograma para exportar.")

st.markdown("---")

