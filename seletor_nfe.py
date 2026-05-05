#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interface gráfica interativa para seleção de XMLs de NF-e e geração de relatório HTML.

Funcionalidades:
  - Navegar por pasta ou selecionar arquivos individualmente
  - Filtros em tempo real por nome e tipo de arquivo
  - Seleção por checkboxes (selecionar todos / desselecionar / inverter)
  - Barra de progresso durante o processamento
  - Abre o relatório HTML automaticamente no navegador

Uso:
    python seletor_nfe.py

Dependências:
    - Python >= 3.8 (tkinter embutido)
    - relatorio_nfe_html.py (no mesmo diretório)

Autor: VIA
Data: 05/05/2026
"""

import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Importa funções do módulo de geração de relatório ────────────────────────
_DIR_SCRIPT = Path(__file__).resolve().parent
if str(_DIR_SCRIPT) not in sys.path:
    sys.path.insert(0, str(_DIR_SCRIPT))

try:
    from relatorio_nfe_html import _extrair_nota, _gerar_html
except ImportError as _eImport:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Módulo não encontrado",
        f"O arquivo 'relatorio_nfe_html.py' precisa estar na mesma pasta.\n\n{_eImport}",
    )
    sys.exit(1)


# ── Constantes ────────────────────────────────────────────────────────────────
EXTENSOES_XML = {".xml"}

# Tipos de arquivo: label → fragmento a buscar no nome
TIPOS_ARQUIVO = {
    "Todos os XMLs":     None,
    "AUTORIZADO":        "AUTORIZADO",
    "NFCe AUTORIZADO":   "NFCeAUTORIZADO",
    "CANCELADO":         "CANCELADO",
    "CORRECAO":          "CORRECAO",
    "GERADO":            "GERADO",
    "ASSINADO":          "ASSINADO",
    "INUTILIZADO":       "INUTILIZADO",
}

COR_PRIMARIA   = "#1a5276"
COR_SELECIONADO = "#d4efdf"
COR_NORMAL      = "#ffffff"
COR_ERRO        = "#fdf2f2"


# ══════════════════════════════════════════════════════════════════════════════
# Classe principal da interface
# ══════════════════════════════════════════════════════════════════════════════

class SeletorNFe:
    """
    Janela principal do seletor de NF-e.

    Estrutura da janela:
      ┌──────────────────────────────────────────────────────┐
      │ Cabeçalho                                            │
      ├──────────────────────────────────────────────────────┤
      │ Pasta: [_______________] [Navegar pasta] [Arquivos]  │
      ├──────────────────────────────────────────────────────┤
      │ Filtros: texto | tipo | [Sel. todos] [Dessel.] [Inv] │
      ├──────────────────────────────────────────────────────┤
      │ ✓ | Nome do arquivo         | Tamanho | Data         │
      │ ─────────────────────────────────────────────────── │
      │ ☑ | 004400_AUTORIZADO.xml   | 12 KB   | 08/11/2024  │
      │ ☑ | 004401_AUTORIZADO.xml   | 15 KB   | 08/11/2024  │
      │ ...                                      (scroll)   │
      ├──────────────────────────────────────────────────────┤
      │ 5 selecionado(s) de 10 visível(is) / 50 total        │
      │ ████████████████░░░░░░░░ 70%                         │
      │ Status: processando...     [Gerar Relatório HTML]    │
      └──────────────────────────────────────────────────────┘
    """

    def __init__(self, oRoot: tk.Tk):
        self.oRoot = oRoot
        self.oRoot.title("Seletor de NF-e – Gerador de Relatório HTML")
        self.oRoot.geometry("1050x730")
        self.oRoot.minsize(800, 560)

        # ── Variáveis de estado ───────────────────────────────────────────────
        self._sCaminhoDir  = tk.StringVar()
        self._sFiltroTexto = tk.StringVar()
        self._sTipoFiltro  = tk.StringVar(value="Todos os XMLs")
        self._sStatusMsg   = tk.StringVar(value="Selecione uma pasta ou arquivos XML.")
        self._bProcessando = False

        # Dados dos arquivos: sIid → dict com path, nome, selecionado, visivel
        self._dArquivos: dict = {}

        self._construir_interface()
        self._aplicar_estilo()

        # Filtros em tempo real
        self._sFiltroTexto.trace_add("write", lambda *_: self._aplicar_filtro())
        self._sTipoFiltro.trace_add("write", lambda *_: self._aplicar_filtro())

    # ──────────────────────────────────────────────────────────────────────────
    # Construção da interface
    # ──────────────────────────────────────────────────────────────────────────

    def _construir_interface(self):
        """Monta todos os frames e widgets da janela."""

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        oFrmHeader = tk.Frame(self.oRoot, bg=COR_PRIMARIA, pady=10)
        oFrmHeader.pack(fill=tk.X)
        tk.Label(
            oFrmHeader,
            text="Seletor de NF-e  –  Gerador de Relatório HTML",
            bg=COR_PRIMARIA, fg="white",
            font=("Segoe UI", 13, "bold"),
        ).pack(padx=16)
        tk.Label(
            oFrmHeader,
            text="Selecione a pasta ou os arquivos XML, aplique filtros e gere o relatório.",
            bg=COR_PRIMARIA, fg="#aed6f1",
            font=("Segoe UI", 9),
        ).pack(padx=16)

        # ── Área central com padding ───────────────────────────────────────────
        oFrmMain = tk.Frame(self.oRoot, padx=10, pady=8)
        oFrmMain.pack(fill=tk.BOTH, expand=True)

        # ── Seleção de pasta / arquivos ────────────────────────────────────────
        oFrmDir = ttk.LabelFrame(oFrmMain, text="Localização dos XMLs", padding=(8, 4))
        oFrmDir.pack(fill=tk.X, pady=(0, 6))

        tk.Label(oFrmDir, text="Pasta:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        oEntDir = ttk.Entry(oFrmDir, textvariable=self._sCaminhoDir, width=72)
        oEntDir.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6))
        oEntDir.bind("<Return>", lambda _e: self._carregar_pasta())
        oFrmDir.columnconfigure(1, weight=1)

        oFrmBotoesDir = tk.Frame(oFrmDir)
        oFrmBotoesDir.grid(row=0, column=2)
        ttk.Button(
            oFrmBotoesDir, text="📁  Navegar pasta",
            command=self._navegar_pasta, width=16,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            oFrmBotoesDir, text="📄  Selecionar arquivos",
            command=self._navegar_arquivos, width=20,
        ).pack(side=tk.LEFT)

        # ── Filtros ────────────────────────────────────────────────────────────
        oFrmFiltros = ttk.LabelFrame(oFrmMain, text="Filtros", padding=(8, 4))
        oFrmFiltros.pack(fill=tk.X, pady=(0, 6))

        # Linha 1: caixas de filtro
        tk.Label(oFrmFiltros, text="Nome contém:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 4))
        ttk.Entry(
            oFrmFiltros, textvariable=self._sFiltroTexto, width=28,
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 14))

        tk.Label(oFrmFiltros, text="Tipo:").grid(
            row=0, column=2, sticky=tk.W, padx=(0, 4))
        oComboTipo = ttk.Combobox(
            oFrmFiltros, textvariable=self._sTipoFiltro,
            values=list(TIPOS_ARQUIVO.keys()), state="readonly", width=22,
        )
        oComboTipo.grid(row=0, column=3, sticky=tk.W, padx=(0, 14))

        ttk.Button(
            oFrmFiltros, text="✕  Limpar filtros",
            command=self._limpar_filtros, width=14,
        ).grid(row=0, column=4, padx=(0, 0))

        # Linha 2: botões de seleção
        oFrmBotoesSel = tk.Frame(oFrmFiltros)
        oFrmBotoesSel.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))
        ttk.Button(
            oFrmBotoesSel, text="☑  Selecionar visíveis",
            command=self._selecionar_todos, width=20,
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            oFrmBotoesSel, text="☐  Desselecionar todos",
            command=self._desselecionar_todos, width=22,
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            oFrmBotoesSel, text="⇄  Inverter seleção",
            command=self._inverter_selecao, width=18,
        ).pack(side=tk.LEFT)

        # ── Lista de arquivos ──────────────────────────────────────────────────
        oFrmLista = ttk.LabelFrame(oFrmMain, text="Arquivos XML", padding=4)
        oFrmLista.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.oTree = ttk.Treeview(
            oFrmLista,
            columns=("sel", "nome", "tamanho", "data"),
            show="headings",
            selectmode="extended",
        )
        self.oTree.heading("sel",     text="✓",             anchor=tk.CENTER)
        self.oTree.heading("nome",    text="Nome do arquivo")
        self.oTree.heading("tamanho", text="Tamanho",        anchor=tk.CENTER)
        self.oTree.heading("data",    text="Data modificação", anchor=tk.CENTER)

        self.oTree.column("sel",     width=36,  minwidth=36,  stretch=False, anchor=tk.CENTER)
        self.oTree.column("nome",    width=500, minwidth=200)
        self.oTree.column("tamanho", width=90,  minwidth=70,  anchor=tk.E)
        self.oTree.column("data",    width=150, minwidth=120, anchor=tk.CENTER)

        # Tags de cores para checked/unchecked
        self.oTree.tag_configure("checked",   background=COR_SELECIONADO)
        self.oTree.tag_configure("unchecked", background=COR_NORMAL)

        oScrollV = ttk.Scrollbar(oFrmLista, orient=tk.VERTICAL,   command=self.oTree.yview)
        oScrollH = ttk.Scrollbar(oFrmLista, orient=tk.HORIZONTAL, command=self.oTree.xview)
        self.oTree.configure(yscrollcommand=oScrollV.set, xscrollcommand=oScrollH.set)

        oScrollV.pack(side=tk.RIGHT,  fill=tk.Y)
        oScrollH.pack(side=tk.BOTTOM, fill=tk.X)
        self.oTree.pack(fill=tk.BOTH, expand=True)

        # Eventos de interação
        self.oTree.bind("<Button-1>",     self._on_click_tree)
        self.oTree.bind("<space>",        self._on_space_tree)
        self.oTree.bind("<Motion>",       self._on_motion_tree)
        self.oTree.bind("<Double-1>",     self._on_double_click_tree)

        # ── Rodapé ────────────────────────────────────────────────────────────
        oFrmRodape = tk.Frame(oFrmMain)
        oFrmRodape.pack(fill=tk.X)

        # Contador
        self._oLblContador = tk.Label(
            oFrmRodape, text="Nenhum arquivo carregado.",
            fg="#555", font=("Segoe UI", 9),
        )
        self._oLblContador.pack(anchor=tk.W)

        # Barra de progresso
        self._oProgress = ttk.Progressbar(oFrmRodape, mode="determinate")
        self._oProgress.pack(fill=tk.X, pady=(4, 4))

        # Status + botão gerar
        oFrmAcoes = tk.Frame(oFrmRodape)
        oFrmAcoes.pack(fill=tk.X)

        tk.Label(
            oFrmAcoes, textvariable=self._sStatusMsg,
            fg="#2980b9", font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, expand=True, anchor=tk.W)

        self._oBtnGerar = ttk.Button(
            oFrmAcoes, text="▶  Gerar Relatório HTML",
            command=self._gerar_relatorio,
        )
        self._oBtnGerar.pack(side=tk.RIGHT, padx=(8, 0))

    def _aplicar_estilo(self):
        """Configura estilos ttk para melhor aparência."""
        oStyle = ttk.Style()
        for sTheme in ("vista", "xpnative", "clam"):
            try:
                oStyle.theme_use(sTheme)
                break
            except Exception:
                continue
        oStyle.configure("Treeview",         rowheight=22, font=("Segoe UI", 10))
        oStyle.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    # ──────────────────────────────────────────────────────────────────────────
    # Carregamento de arquivos
    # ──────────────────────────────────────────────────────────────────────────

    def _navegar_pasta(self):
        """Abre diálogo de seleção de pasta e carrega todos os XMLs encontrados."""
        sPasta = filedialog.askdirectory(
            title="Selecionar pasta com XMLs",
            initialdir=self._sCaminhoDir.get() or str(Path.home()),
        )
        if sPasta:
            self._sCaminhoDir.set(sPasta)
            self._carregar_pasta()

    def _navegar_arquivos(self):
        """Abre diálogo de seleção múltipla de arquivos XML."""
        sInicial = self._sCaminhoDir.get() or str(Path.home())
        aTupla = filedialog.askopenfilenames(
            title="Selecionar arquivos XML de NF-e",
            initialdir=sInicial,
            filetypes=[("Arquivos XML", "*.xml *.XML"), ("Todos os arquivos", "*.*")],
        )
        if aTupla:
            self._sCaminhoDir.set(str(Path(aTupla[0]).parent))
            self._carregar_lista_arquivos(list(aTupla))

    def _carregar_pasta(self):
        """Lê o campo de pasta e carrega todos os XMLs encontrados (recursivo)."""
        sPasta = self._sCaminhoDir.get().strip()
        if not sPasta:
            return
        oPasta = Path(sPasta)
        if not oPasta.is_dir():
            messagebox.showerror(
                "Pasta inválida",
                f"O caminho informado não é uma pasta válida:\n{sPasta}",
            )
            return

        self._sStatusMsg.set("Buscando arquivos XML...")
        self.oRoot.update_idletasks()

        aArquivos = sorted(
            (str(p) for p in oPasta.rglob("*") if p.suffix.lower() in EXTENSOES_XML),
            key=lambda s: Path(s).name.lower(),
        )

        if not aArquivos:
            messagebox.showinfo("Sem arquivos", "Nenhum arquivo XML encontrado na pasta.")
            self._sStatusMsg.set("Nenhum arquivo XML encontrado.")
            return

        self._carregar_lista_arquivos(aArquivos)

    def _carregar_lista_arquivos(self, aCaminhos: list):
        """
        Popula o Treeview com os arquivos informados.

        Todos os itens começam selecionados (☑).

        Args:
            aCaminhos: Lista de caminhos absolutos de arquivos XML.
        """
        # Limpa estado anterior
        for sIid in self.oTree.get_children():
            self.oTree.delete(sIid)
        self._dArquivos.clear()

        for sCaminho in aCaminhos:
            oPath = Path(sCaminho)
            sTamanho, sData = self._meta_arquivo(oPath)
            sNome = oPath.name

            sIid = self.oTree.insert(
                "", tk.END,
                values=("☑", sNome, sTamanho, sData),
                tags=("checked",),
            )
            self._dArquivos[sIid] = {
                "path":       oPath,
                "nome":       sNome,
                "selecionado": True,
                "visivel":     True,
            }

        self._aplicar_filtro()
        self._sStatusMsg.set(f"{len(aCaminhos)} arquivo(s) carregado(s). Pronto.")

    # ──────────────────────────────────────────────────────────────────────────
    # Filtros em tempo real
    # ──────────────────────────────────────────────────────────────────────────

    def _aplicar_filtro(self):
        """
        Aplica filtros de texto e tipo em tempo real usando detach/reattach.
        Itens ocultos mantêm seu estado de seleção.
        """
        sTexto = self._sFiltroTexto.get().strip().lower()
        sTipo  = TIPOS_ARQUIVO.get(self._sTipoFiltro.get())

        # Destaca todos primeiro (sem deletar)
        for sIid in list(self.oTree.get_children()):
            self.oTree.detach(sIid)

        # Reanexa somente os que passam nos filtros, na ordem original
        for sIid, oDados in self._dArquivos.items():
            sNome = oDados["nome"].lower()
            bPassaTexto = (not sTexto) or (sTexto in sNome)
            bPassaTipo  = (not sTipo)  or (sTipo.lower() in sNome)
            bVisivel    = bPassaTexto and bPassaTipo

            oDados["visivel"] = bVisivel
            if bVisivel:
                self.oTree.reattach(sIid, "", tk.END)

        self._atualizar_contador()

    def _limpar_filtros(self):
        """Remove filtros de texto e tipo."""
        self._sFiltroTexto.set("")
        self._sTipoFiltro.set("Todos os XMLs")

    # ──────────────────────────────────────────────────────────────────────────
    # Seleção / Toggle de checkboxes
    # ──────────────────────────────────────────────────────────────────────────

    def _toggle_item(self, sIid: str):
        """Inverte o estado de seleção de um item do Treeview."""
        if sIid not in self._dArquivos:
            return
        oDados = self._dArquivos[sIid]
        bNovo  = not oDados["selecionado"]
        oDados["selecionado"] = bNovo
        sSel = "☑" if bNovo else "☐"
        sTag = "checked" if bNovo else "unchecked"
        oVals = self.oTree.item(sIid, "values")
        self.oTree.item(sIid, values=(sSel, oVals[1], oVals[2], oVals[3]), tags=(sTag,))
        self._atualizar_contador()

    def _on_click_tree(self, oEvt):
        """Toggle na coluna ☑ (coluna #1) ao clicar."""
        sRegiao = self.oTree.identify_region(oEvt.x, oEvt.y)
        sCol    = self.oTree.identify_column(oEvt.x)
        sIid    = self.oTree.identify_row(oEvt.y)
        if sIid and sRegiao == "cell" and sCol == "#1":
            self._toggle_item(sIid)

    def _on_double_click_tree(self, oEvt):
        """Duplo clique em qualquer coluna também alterna o checkbox."""
        sCol = self.oTree.identify_column(oEvt.x)
        sIid = self.oTree.identify_row(oEvt.y)
        if sIid and sCol != "#1":  # coluna #1 já tratada pelo _on_click_tree
            self._toggle_item(sIid)

    def _on_space_tree(self, _oEvt):
        """Barra de espaço alterna os itens selecionados pelo teclado."""
        for sIid in self.oTree.selection():
            self._toggle_item(sIid)

    def _on_motion_tree(self, oEvt):
        """Exibe o caminho completo do arquivo na barra de status ao passar o mouse."""
        sIid = self.oTree.identify_row(oEvt.y)
        if sIid and sIid in self._dArquivos:
            sCaminho = str(self._dArquivos[sIid]["path"])
            self._sStatusMsg.set(sCaminho)

    def _selecionar_todos(self):
        """Marca todos os itens visíveis (que passam no filtro atual)."""
        for sIid in self.oTree.get_children():
            if not self._dArquivos[sIid]["selecionado"]:
                self._toggle_item(sIid)

    def _desselecionar_todos(self):
        """Desmarca todos os itens (visíveis e ocultos)."""
        for sIid, oDados in self._dArquivos.items():
            if oDados["selecionado"]:
                oDados["selecionado"] = False
                if self.oTree.exists(sIid):
                    oVals = self.oTree.item(sIid, "values")
                    self.oTree.item(sIid, values=("☐", oVals[1], oVals[2], oVals[3]),
                                    tags=("unchecked",))
        self._atualizar_contador()

    def _inverter_selecao(self):
        """Inverte a seleção dos itens visíveis."""
        for sIid in self.oTree.get_children():
            self._toggle_item(sIid)

    def _atualizar_contador(self):
        """Atualiza o label com a contagem de selecionados/visíveis/total."""
        iSel   = sum(1 for o in self._dArquivos.values() if o["selecionado"])
        iVis   = sum(1 for o in self._dArquivos.values() if o["visivel"])
        iTotal = len(self._dArquivos)
        self._oLblContador.config(
            text=f"{iSel} selecionado(s)  |  {iVis} visível(is) (filtro)  |  {iTotal} total",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Geração do relatório HTML
    # ──────────────────────────────────────────────────────────────────────────

    def _gerar_relatorio(self):
        """Valida a seleção e dispara o processamento em thread separada."""
        if self._bProcessando:
            return

        aSelecionados = [
            str(oDados["path"])
            for oDados in self._dArquivos.values()
            if oDados["selecionado"]
        ]

        if not aSelecionados:
            messagebox.showwarning(
                "Nenhum arquivo selecionado",
                "Selecione ao menos um arquivo XML antes de gerar o relatório.",
            )
            return

        # Solicita pasta de saída (padrão: mesma pasta dos XMLs)
        sPadraoPasta = self._sCaminhoDir.get() or str(Path(aSelecionados[0]).parent)
        sPastaSaida = filedialog.askdirectory(
            title="Onde salvar o relatório HTML?",
            initialdir=sPadraoPasta,
        )
        if not sPastaSaida:
            return  # Usuário cancelou

        self._bProcessando = True
        self._oBtnGerar.config(state=tk.DISABLED)
        self._oProgress.config(value=0, maximum=len(aSelecionados))
        self._sStatusMsg.set(f"Iniciando processamento de {len(aSelecionados)} arquivo(s)...")

        oThread = threading.Thread(
            target=self._processar_em_thread,
            args=(aSelecionados, sPastaSaida),
            daemon=True,
        )
        oThread.start()

    def _processar_em_thread(self, aCaminhos: list, sPastaSaida: str):
        """
        Processa os XMLs e gera o HTML em thread separada,
        atualizando a UI via oRoot.after() para thread-safety.

        Args:
            aCaminhos:    Lista de caminhos absolutos selecionados.
            sPastaSaida:  Pasta onde o arquivo HTML será salvo.
        """
        aNotas: list = []
        aErros: list = []
        iTotal = len(aCaminhos)

        for iIdx, sCaminho in enumerate(aCaminhos, 1):
            sNome = Path(sCaminho).name
            self.oRoot.after(
                0, self._sStatusMsg.set,
                f"[{iIdx}/{iTotal}]  Processando: {sNome}",
            )
            self.oRoot.after(0, self._oProgress.config, {"value": iIdx - 1})

            try:
                oNota = _extrair_nota(sCaminho)
                aNotas.append(oNota)
            except Exception as oEx:
                aErros.append({
                    "caminho": sCaminho,
                    "erro":    f"{type(oEx).__name__}: {oEx}",
                })

        # Gera o HTML
        self.oRoot.after(0, self._sStatusMsg.set, "Montando HTML...")
        try:
            sDtStamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
            sSaida     = str(Path(sPastaSaida) / f"relatorio_nfe_{sDtStamp}.html")
            sDescricao = f"Seleção manual – {iTotal} arquivo(s)"

            sHtml = _gerar_html(aNotas, aErros, sDescricao)
            with open(sSaida, "w", encoding="utf-8") as oArq:
                oArq.write(sHtml)

            self.oRoot.after(0, self._oProgress.config, {"value": iTotal})
            self.oRoot.after(
                0, self._sStatusMsg.set,
                f"Relatório gerado: {Path(sSaida).name}  |  "
                f"✓ {len(aNotas)} nota(s)  |  ✗ {len(aErros)} erro(s)",
            )

            # Abre no navegador
            webbrowser.open(Path(sSaida).as_uri())

            # Feedback ao usuário
            sMsgErros = (
                f"\n\n⚠ {len(aErros)} arquivo(s) com erro (listados no relatório)."
                if aErros else ""
            )
            self.oRoot.after(
                0,
                lambda: messagebox.showinfo(
                    "Relatório gerado",
                    f"✓  {len(aNotas)} nota(s) processada(s) com sucesso."
                    f"{sMsgErros}\n\n"
                    f"Arquivo salvo em:\n{sSaida}",
                ),
            )

        except Exception as oEx:
            self.oRoot.after(
                0,
                lambda: messagebox.showerror(
                    "Erro na geração do relatório",
                    f"Ocorreu um erro ao gerar o HTML:\n\n{type(oEx).__name__}: {oEx}",
                ),
            )
            self.oRoot.after(0, self._sStatusMsg.set, f"Erro: {oEx}")

        finally:
            self.oRoot.after(0, self._finalizar_processamento)

    def _finalizar_processamento(self):
        """Restaura o estado da UI após o processamento."""
        self._bProcessando = False
        self._oBtnGerar.config(state=tk.NORMAL)

    # ──────────────────────────────────────────────────────────────────────────
    # Utilitários
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _meta_arquivo(oPath: Path) -> tuple:
        """Retorna (tamanho formatado, data modificação formatada) de um arquivo."""
        try:
            oStat    = oPath.stat()
            iBytes   = oStat.st_size
            sTamanho = (
                f"{iBytes/1024:.1f} KB"
                if iBytes < 1_048_576
                else f"{iBytes/1_048_576:.1f} MB"
            )
            sData = datetime.fromtimestamp(oStat.st_mtime).strftime("%d/%m/%Y %H:%M")
        except Exception:
            sTamanho = "—"
            sData    = "—"
        return sTamanho, sData


# ══════════════════════════════════════════════════════════════════════════════
# Ponto de entrada
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Inicializa e executa a interface gráfica."""
    oRoot = tk.Tk()
    # Ícone padrão do sistema quando disponível
    try:
        oRoot.iconbitmap(default="")
    except Exception:
        pass
    _oApp = SeletorNFe(oRoot)
    oRoot.mainloop()


if __name__ == "__main__":
    main()
