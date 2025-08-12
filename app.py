# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Gerador de Cronograma - Embalagens", layout="wide")

st.title("Gerador automático de cronogramas — Embalagens")
st.markdown(
    """
    Faça upload do Excel com as tarefas (colunas esperadas: Número, Classificação, Categoria, Fase, Condição, Nome, Duração ...)
    - Tarefas com **Condição = 'Sempre'** serão sempre incluídas.
    - Você pode escolher A/B/C por fase.
    """
)

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
            df_raw = pd.read_csv(uploaded, sep=";")
        else:
            df_raw = pd.read_excel(uploaded, engine='openpyxl', sep=";")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        st.stop()
else:
    st.info("Nenhum arquivo carregado ainda — usando um exemplo pequeno para demonstração.")
    # exemplo mínimo
    sample = {
        'Número': [1,2,3,4,5,6],
        'Classificação': ['Embalagem Primária']*6,
        'Categoria': ['Ampolas']*6,
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
    # mostramos as colunas detectadas para ajudar
    st.write("Colunas detectadas no arquivo:", df_raw.columns.tolist())

# normaliza duracao
if 'duracao' in df.columns:
    # Converter "5 dias" para número inteiro (5)
    df["Duração_num"] = df["Duração"].str.replace(" dias", "").astype(int)

# Se quiser transformar em timedelta (ex: útil para somar datas)
    df["Duração_tempo"] = pd.to_timedelta(df["Duração_num"], unit="D")
else:
    st.error("Coluna de duração não encontrada — não é possível continuar.")
    st.stop()

# padroniza valores de condição
df['condicao'] = df['condicao'].astype(str).str.strip()

# ---------- Filtros básicos ----------
st.sidebar.header("Filtros do projeto")
start_date = st.sidebar.date_input("Data de início do projeto", value=pd.Timestamp.today().date())
categoria_options = ['Todos'] + sorted(df['categoria'].dropna().unique().tolist()) if 'categoria' in df.columns else ['Todos']
selected_categoria = st.sidebar.selectbox("Categoria do projeto (filtrar)", categoria_options, index=0)

if selected_categoria != 'Todos' and 'categoria' in df.columns:
    df = df[df['categoria'] == selected_categoria]

# fases disponíveis
phases = list(df['fase'].dropna().unique())
phases_ordered = phases  # mantemos ordem de aparição
st.sidebar.markdown(f"**Fases detectadas:** {len(phases_ordered)}")

# Para cada fase, permite escolher condições A/B/C (Sempre é sempre incluída)
st.sidebar.subheader("Condições por fase (Sempre é sempre incluída)")
phase_conditions = {}
possible_conditions = sorted(list(df['condicao'].dropna().unique()))
# remove 'Sempre' das opções para seleção (ela será sempre adicionada)
option_conditions = [c for c in possible_conditions if c.lower() != 'sempre']
if not option_conditions:
    option_conditions = ['A','B','C']  # fallback

for ph in phases_ordered:
    # preseleciona todos
    sel = st.sidebar.multiselect(f"{ph}", options=option_conditions, default=option_conditions, key=f"cond_{ph}")
    # sempre incluir 'Sempre'
    if 'Sempre' in possible_conditions or 'sempre' in [x.lower() for x in possible_conditions]:
        sel = list(set(sel + ['Sempre']))
    phase_conditions[ph] = sel

chain_seq = st.sidebar.checkbox("Encadear tarefas sequencialmente (uma continua após a outra)", value=True)
st.sidebar.markdown("Se desmarcado: cada fase começa na data inicial (pode haver tarefas paralelas entre fases).")

# ---------- Montar lista de tarefas de saída ----------
# Filtra por fase + condições escolhidas
selected_rows = []
for ph in phases_ordered:
    conds = phase_conditions.get(ph, [])
    # normaliza comparação (caso letras minúsculas)
    conds_norm = [c.lower() for c in conds]
    # seleciona linhas: condicao == 'sempre' OR condicao in selected conditions
    df_ph = df[df['fase'] == ph].copy()
    # include if condicao lower in conds_norm OR condicao == 'sempre'
    mask = df_ph['condicao'].astype(str).str.lower().isin(conds_norm) | (df_ph['condicao'].astype(str).str.lower() == 'sempre')
    df_ph = df_ph[mask]
    selected_rows.append(df_ph)

if selected_rows:
    df_sel = pd.concat(selected_rows, ignore_index=True)
else:
    df_sel = df.iloc[0:0].copy()

# Ordena por fase (pela ordem detectada) e por número se existir
if 'numero' in df_sel.columns:
    # cria ordem numérica da fase
    phase_order_map = {ph: i for i, ph in enumerate(phases_ordered)}
    df_sel['phase_order'] = df_sel['fase'].map(phase_order_map)
    df_sel = df_sel.sort_values(by=['phase_order', 'numero']).reset_index(drop=True)
    df_sel = df_sel.drop(columns=['phase_order'])
else:
    df_sel = df_sel.reset_index(drop=True)

st.header("Resumo das tarefas selecionadas")
st.write(f"Tarefas selecionadas: {len(df_sel)}")
st.dataframe(df_sel[['numero','fase','condicao','nome','duracao']].fillna('') if 'numero' in df_sel.columns else df_sel[['fase','condicao','nome','duracao']].fillna(''))

# ---------- Calcular datas (sequencial ou por fase) ----------
project_start = pd.to_datetime(start_date)

if chain_seq:
    # cálculo sequencial único (todas as tarefas em uma linha temporal)
    durations = df_sel['duracao'].astype(float).fillna(1)
    start_offsets = durations.cumsum() - durations  # start offset days
    df_sel['start'] = project_start + pd.to_timedelta(start_offsets, unit='D')
    df_sel['end'] = df_sel['start'] + pd.to_timedelta(durations, unit='D')
else:
    # por fase: cada fase reinicia sua contagem a partir do project_start -> provoca sobreposição
    starts = []
    ends = []
    for ph in phases_ordered:
        df_ph = df_sel[df_sel['fase'] == ph].copy()
        if df_ph.empty:
            continue
        durations = df_ph['duracao'].astype(float).fillna(1)
        start_offsets = durations.cumsum() - durations
        starts_ph = project_start + pd.to_timedelta(start_offsets, unit='D')
        ends_ph = starts_ph + pd.to_timedelta(durations, unit='D')
        # assign back
        df_sel.loc[df_ph.index, 'start'] = starts_ph
        df_sel.loc[df_ph.index, 'end'] = ends_ph

# Garantir colunas datetime
df_sel['start'] = pd.to_datetime(df_sel['start'])
df_sel['end'] = pd.to_datetime(df_sel['end'])

# ---------- Visualização Gantt (Plotly) ----------
st.header("Cronograma (Gantt)")
if df_sel.empty:
    st.info("Nenhuma tarefa selecionada para gerar cronograma.")
else:
    # px.timeline prefere y = tarefa; para agrupar por fase usamos facet or y=phase e text=nome
    # ordenar tarefas por start
    df_plot = df_sel.sort_values('start').copy()
    # criar label curta para cada linha
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
    fig.update_yaxes(autorange="reversed")  # Gantt top-to-bottom
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # resumo de duração total
    total_days = (df_sel['end'].max() - df_sel['start'].min()).days
    st.write(f"Duração total do cronograma (dias, intervalo entre 1ª e última tarefa): **{total_days}** dias")

# ---------- Download / Export ----------
st.header("Exportar cronograma")
if not df_sel.empty:
    # CSV
    csv = df_sel.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar CSV", data=csv, file_name="cronograma.csv", mime="text/csv")
    # Excel
    towrite = BytesIO()
    with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
        df_sel.to_excel(writer, index=False, sheet_name='cronograma')

    towrite.seek(0)
    st.download_button("📥 Baixar XLSX", data=towrite, file_name="cronograma.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Nenhum cronograma para exportar.")

st.markdown("---")
st.caption("Observações: este app é um ponto de partida. O algoritmo atual agenda tarefas de forma sequencial por fase. Dependendo do requisito (recursos paralelos, dependências entre tarefas, restrições de recursos), você pode evoluir para um algoritmo de scheduling (CP-SAT, programação linear, heurísticas, etc.).")
