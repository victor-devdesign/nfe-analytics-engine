#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para processar arquivos XML de Notas Fiscais Eletrônicas (NF-e)
e gerar um relatório HTML consolidado.

Uso:
    python relatorio_nfe_html.py <arquivo_lista.txt>
    python relatorio_nfe_html.py  (solicita o arquivo interativamente)

Formato do arquivo .txt:
    Uma linha por XML (caminho absoluto ou relativo):
    C:\\caminho\\para\\nota1.xml
    C:\\caminho\\para\\nota2.xml
    ...

Autor: VIA
Data: 05/05/2026
"""

import os
import sys
import xml.etree.ElementTree as ET
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Namespace padrão das NF-e ────────────────────────────────────────────────
NS = "http://www.portalfiscal.inf.br/nfe"
NSP = f"{{{NS}}}"      # prefixo no formato {uri}tag


# ══════════════════════════════════════════════════════════════════════════════
# Funções auxiliares de extração XML
# ══════════════════════════════════════════════════════════════════════════════

def _find_text(root: ET.Element, *caminhos: str) -> str:
    """
    Tenta encontrar o texto de um elemento XML testando múltiplos caminhos XPath.
    Suporta busca com e sem namespace automaticamente.

    Args:
        root:      Elemento raiz (ou sub-elemento) de busca.
        *caminhos: Um ou mais caminhos XPath relativos, separados por '/'.

    Returns:
        Texto do primeiro elemento encontrado, ou string vazia.
    """
    for caminho in caminhos:
        # Tenta sem namespace
        el = root.find(f".//{caminho}")
        if el is not None and el.text:
            return el.text.strip()
        # Tenta com namespace em cada parte
        partes = caminho.split("/")
        xpath_ns = "/".join(f"{NSP}{p}" for p in partes)
        el = root.find(f".//{xpath_ns}")
        if el is not None and el.text:
            return el.text.strip()
    return ""


def _find_all(root: ET.Element, caminho: str):
    """
    Retorna todos os elementos correspondentes ao caminho, com ou sem namespace.

    Args:
        root:    Elemento raiz de busca.
        caminho: Caminho XPath (tag simples ou com '/').

    Returns:
        Lista de elementos ET.Element.
    """
    # Sem namespace
    resultado = root.findall(f".//{caminho}")
    if resultado:
        return resultado
    # Com namespace
    partes = caminho.split("/")
    xpath_ns = "/".join(f"{NSP}{p}" for p in partes)
    return root.findall(f".//{xpath_ns}")


def _formatar_cnpj(sNumero: str) -> str:
    """Formata CNPJ: 14 dígitos → XX.XXX.XXX/XXXX-XX"""
    sD = "".join(c for c in sNumero if c.isdigit())
    if len(sD) == 14:
        return f"{sD[:2]}.{sD[2:5]}.{sD[5:8]}/{sD[8:12]}-{sD[12:]}"
    return sNumero


def _formatar_cpf(sNumero: str) -> str:
    """Formata CPF: 11 dígitos → XXX.XXX.XXX-XX"""
    sD = "".join(c for c in sNumero if c.isdigit())
    if len(sD) == 11:
        return f"{sD[:3]}.{sD[3:6]}.{sD[6:9]}-{sD[9:]}"
    return sNumero


def _formatar_fone(sFone: str) -> str:
    """Formata telefone: 10/11 dígitos → (XX) XXXXX-XXXX"""
    sD = "".join(c for c in sFone if c.isdigit())
    if len(sD) == 11:
        return f"({sD[:2]}) {sD[2:7]}-{sD[7:]}"
    if len(sD) == 10:
        return f"({sD[:2]}) {sD[2:6]}-{sD[6:]}"
    return sFone


def _formatar_data(sData: str) -> str:
    """Converte ISO 8601 → DD/MM/YYYY HH:MM"""
    try:
        sD = sData[:16].replace("T", " ")
        dt = datetime.strptime(sD, "%Y-%m-%d %H:%M")
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return sData


def _moeda(sValor: str) -> str:
    """Formata valor como moeda brasileira → R$ 1.234,56"""
    try:
        fV = float(sValor)
        return f"R$ {fV:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return sValor or "—"


def _pct(sValor: str) -> str:
    """Formata percentual → 18,00%"""
    try:
        return f"{float(sValor):.2f}%".replace(".", ",")
    except Exception:
        return sValor or "—"


# ══════════════════════════════════════════════════════════════════════════════
# Extração dos dados da NF-e
# ══════════════════════════════════════════════════════════════════════════════

def _extrair_endereco(oEl: ET.Element) -> str:
    """Monta string de endereço a partir de um elemento enderEmit ou enderDest."""
    sLgr    = _find_text(oEl, "xLgr")
    sNro    = _find_text(oEl, "nro")
    sCpl    = _find_text(oEl, "xCpl")
    sBairro = _find_text(oEl, "xBairro")
    sMun    = _find_text(oEl, "xMun")
    sUf     = _find_text(oEl, "UF")
    sCep    = _find_text(oEl, "CEP")

    sEnd = f"{sLgr}, {sNro}"
    if sCpl:
        sEnd += f" – {sCpl}"
    sEnd += f", {sBairro}, {sMun}/{sUf}"
    if sCep and len(sCep) == 8:
        sEnd += f" – CEP {sCep[:5]}-{sCep[5:]}"
    return sEnd


def _extrair_participante(oEl: ET.Element, sTipoEnder: str) -> dict:
    """
    Extrai dados de emissor (emit) ou destinatário (dest).

    Args:
        oEl:       Elemento XML <emit> ou <dest>.
        sTipoEnder: 'enderEmit' ou 'enderDest'.

    Returns:
        Dicionário com CNPJ/CPF, razão social, endereço, telefone, e-mail.
    """
    sCnpj  = _find_text(oEl, "CNPJ")
    sCpf   = _find_text(oEl, "CPF")
    sNome  = _find_text(oEl, "xNome")
    sEmail = _find_text(oEl, "email")
    sFone  = _find_text(oEl, "fone", f"{sTipoEnder}/fone")

    # Endereço
    oEnder = oEl.find(f".//{sTipoEnder}") or oEl.find(f".//{NSP}{sTipoEnder}")
    sEndereco = _extrair_endereco(oEnder) if oEnder is not None else ""

    return {
        "documento": _formatar_cnpj(sCnpj) if sCnpj else _formatar_cpf(sCpf),
        "tipo_doc":  "CNPJ" if sCnpj else "CPF",
        "razao":     sNome,
        "endereco":  sEndereco,
        "fone":      _formatar_fone(sFone) if sFone else "",
        "email":     sEmail,
    }


def _extrair_imposto_item(oImposto: ET.Element) -> dict:
    """
    Extrai alíquotas e valores de ICMS, PIS, COFINS e IPI de um elemento <imposto>.

    Returns:
        Dicionário com campos de cada tributo.
    """
    oIcms   = dict(bc="", aliq="", valor="", cst="")
    oPis    = dict(bc="", aliq="", valor="", cst="")
    oCofins = dict(bc="", aliq="", valor="", cst="")
    oIpi    = dict(bc="", aliq="", valor="", cst="")

    if oImposto is None:
        return dict(icms=oIcms, pis=oPis, cofins=oCofins, ipi=oIpi)

    # ICMS – qualquer sub-tag (ICMS00, ICMS10, ICMS40, etc.)
    oIcmsEl = (oImposto.find(".//ICMS") or oImposto.find(f".//{NSP}ICMS"))
    if oIcmsEl is not None:
        oIcms["bc"]    = _find_text(oIcmsEl, "vBC")
        oIcms["aliq"]  = _find_text(oIcmsEl, "pICMS")
        oIcms["valor"] = _find_text(oIcmsEl, "vICMS")
        oIcms["cst"]   = _find_text(oIcmsEl, "CST")

    # PIS
    oPisEl = (oImposto.find(".//PIS") or oImposto.find(f".//{NSP}PIS"))
    if oPisEl is not None:
        oPis["bc"]    = _find_text(oPisEl, "vBC")
        oPis["aliq"]  = _find_text(oPisEl, "pPIS")
        oPis["valor"] = _find_text(oPisEl, "vPIS")
        oPis["cst"]   = _find_text(oPisEl, "CST")

    # COFINS
    oCofinsEl = (oImposto.find(".//COFINS") or oImposto.find(f".//{NSP}COFINS"))
    if oCofinsEl is not None:
        oCofins["bc"]    = _find_text(oCofinsEl, "vBC")
        oCofins["aliq"]  = _find_text(oCofinsEl, "pCOFINS")
        oCofins["valor"] = _find_text(oCofinsEl, "vCOFINS")
        oCofins["cst"]   = _find_text(oCofinsEl, "CST")

    # IPI
    oIpiEl = (oImposto.find(".//IPI") or oImposto.find(f".//{NSP}IPI"))
    if oIpiEl is not None:
        oIpi["bc"]    = _find_text(oIpiEl, "vBC")
        oIpi["aliq"]  = _find_text(oIpiEl, "pIPI")
        oIpi["valor"] = _find_text(oIpiEl, "vIPI")
        oIpi["cst"]   = _find_text(oIpiEl, "CST")

    return dict(icms=oIcms, pis=oPis, cofins=oCofins, ipi=oIpi)


def _extrair_nota(sCaminho: str) -> dict:
    """
    Extrai todos os dados relevantes de um arquivo XML de NF-e.

    Args:
        sCaminho: Caminho local do arquivo XML.

    Returns:
        Dicionário com todos os dados da nota.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ET.ParseError:     Se o XML for inválido.
    """
    sArquivo = Path(sCaminho)
    if not sArquivo.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {sCaminho}")

    oTree = ET.parse(str(sArquivo))
    oRoot = oTree.getroot()

    # Localiza <infNFe> (pode estar dentro de <NFe> ou <nfeProc>)
    oInfNFe = (
        oRoot.find(".//infNFe")
        or oRoot.find(f".//{NSP}infNFe")
    )
    if oInfNFe is None:
        raise ValueError("Elemento <infNFe> não encontrado no XML.")

    # ── Cabeçalho / Identificação (ide) ──────────────────────────────────────
    oIde = oInfNFe.find("ide") or oInfNFe.find(f"{NSP}ide")
    sChave = (oInfNFe.get("Id") or "").replace("NFe", "")

    oResumo = {
        "chave":    sChave,
        "numero":   _find_text(oIde, "nNF")        if oIde is not None else "",
        "serie":    _find_text(oIde, "serie")       if oIde is not None else "",
        "dhEmi":    _find_text(oIde, "dhEmi")       if oIde is not None else "",
        "natOp":    _find_text(oIde, "natOp")       if oIde is not None else "",
        "tpNF":     _find_text(oIde, "tpNF")        if oIde is not None else "",
        "mod":      _find_text(oIde, "mod")         if oIde is not None else "",
    }

    # ── Emissor ───────────────────────────────────────────────────────────────
    oEmit = oInfNFe.find("emit") or oInfNFe.find(f"{NSP}emit")
    oEmissor = _extrair_participante(oEmit, "enderEmit") if oEmit is not None else {}

    # ── Destinatário / Tomador ────────────────────────────────────────────────
    oDest = oInfNFe.find("dest") or oInfNFe.find(f"{NSP}dest")
    oTomador = _extrair_participante(oDest, "enderDest") if oDest is not None else {}

    # ── Itens (det) ───────────────────────────────────────────────────────────
    aItens = []
    for oDet in _find_all(oInfNFe, "det"):
        oProd    = oDet.find("prod")    or oDet.find(f"{NSP}prod")
        oImpost  = oDet.find("imposto") or oDet.find(f"{NSP}imposto")

        oItem = {
            "nItem":    oDet.get("nItem", ""),
            "codigo":   _find_text(oProd, "cProd")  if oProd is not None else "",
            "descricao":_find_text(oProd, "xProd")  if oProd is not None else "",
            "ncm":      _find_text(oProd, "NCM")    if oProd is not None else "",
            "cfop":     _find_text(oProd, "CFOP")   if oProd is not None else "",
            "unidade":  _find_text(oProd, "uCom")   if oProd is not None else "",
            "qtd":      _find_text(oProd, "qCom")   if oProd is not None else "",
            "vUnit":    _find_text(oProd, "vUnCom") if oProd is not None else "",
            "vProd":    _find_text(oProd, "vProd")  if oProd is not None else "",
            "vFrete":   _find_text(oProd, "vFrete") if oProd is not None else "",
            "vDesc":    _find_text(oProd, "vDesc")  if oProd is not None else "",
            "vTotTrib": _find_text(oImpost, "vTotTrib") if oImpost is not None else "",
            "impostos": _extrair_imposto_item(oImpost),
        }
        aItens.append(oItem)

    # ── Totais da nota ─────────────────────────────────────────────────────────
    oICMSTot = oInfNFe.find(".//ICMSTot") or oInfNFe.find(f".//{NSP}ICMSTot")
    oTotais = {
        "vProd":   _find_text(oICMSTot, "vProd")   if oICMSTot is not None else "",
        "vFrete":  _find_text(oICMSTot, "vFrete")  if oICMSTot is not None else "",
        "vDesc":   _find_text(oICMSTot, "vDesc")   if oICMSTot is not None else "",
        "vNF":     _find_text(oICMSTot, "vNF")     if oICMSTot is not None else "",
        "vICMS":   _find_text(oICMSTot, "vICMS")   if oICMSTot is not None else "",
        "vIPI":    _find_text(oICMSTot, "vIPI")    if oICMSTot is not None else "",
        "vPIS":    _find_text(oICMSTot, "vPIS")    if oICMSTot is not None else "",
        "vCOFINS": _find_text(oICMSTot, "vCOFINS") if oICMSTot is not None else "",
        "vST":     _find_text(oICMSTot, "vST")     if oICMSTot is not None else "",
        "vTotTrib":_find_text(oICMSTot, "vTotTrib") if oICMSTot is not None else "",
    }

    # ── Observações (infAdic) ─────────────────────────────────────────────────
    sObsCpl   = _find_text(oInfNFe, "infCpl")
    sObsFisco = _find_text(oInfNFe, "infAdFisco")

    return {
        "arquivo":  str(sArquivo.name),
        "caminho":  str(sCaminho),
        "resumo":   oResumo,
        "emissor":  oEmissor,
        "tomador":  oTomador,
        "itens":    aItens,
        "totais":   oTotais,
        "obs_cpl":  sObsCpl,
        "obs_fisco":sObsFisco,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Geração do HTML
# ══════════════════════════════════════════════════════════════════════════════

def _html_participante(oP: dict, sTitulo: str) -> str:
    """Gera bloco HTML de emissor ou tomador."""
    aLinhas = [
        f"<h4>{sTitulo}</h4>",
        "<table class='tbl-info'>",
        f"<tr><th>{oP.get('tipo_doc','Documento')}</th><td>{oP.get('documento','—')}</td></tr>",
        f"<tr><th>Razão social</th><td>{oP.get('razao','—')}</td></tr>",
        f"<tr><th>Endereço</th><td>{oP.get('endereco','—')}</td></tr>",
    ]
    if oP.get("fone"):
        aLinhas.append(f"<tr><th>Telefone</th><td>{oP['fone']}</td></tr>")
    if oP.get("email"):
        aLinhas.append(f"<tr><th>E-mail</th><td>{oP['email']}</td></tr>")
    aLinhas.append("</table>")
    return "\n".join(aLinhas)


def _html_itens(aItens: list) -> str:
    """Gera tabela HTML de itens da nota."""
    if not aItens:
        return "<p class='vazio'>Nenhum item encontrado.</p>"

    sCabecalho = """
    <table class='tbl-itens'>
        <thead>
            <tr>
                <th>#</th>
                <th>Código</th>
                <th>Descrição</th>
                <th>NCM</th>
                <th>CFOP</th>
                <th>Un</th>
                <th>Qtd</th>
                <th>V. Unit.</th>
                <th>V. Prod.</th>
                <th>ICMS %</th>
                <th>ICMS R$</th>
                <th>PIS %</th>
                <th>PIS R$</th>
                <th>COFINS %</th>
                <th>COFINS R$</th>
                <th>IPI R$</th>
            </tr>
        </thead>
        <tbody>
    """

    aLinhas = [sCabecalho]
    for oIt in aItens:
        oImp = oIt["impostos"]
        aLinhas.append(f"""
            <tr>
                <td class='center'>{oIt['nItem']}</td>
                <td class='center'>{oIt['codigo']}</td>
                <td>{oIt['descricao']}</td>
                <td class='center'>{oIt['ncm']}</td>
                <td class='center'>{oIt['cfop']}</td>
                <td class='center'>{oIt['unidade']}</td>
                <td class='right'>{oIt['qtd']}</td>
                <td class='right'>{_moeda(oIt['vUnit'])}</td>
                <td class='right'>{_moeda(oIt['vProd'])}</td>
                <td class='right'>{_pct(oImp['icms']['aliq'])}</td>
                <td class='right'>{_moeda(oImp['icms']['valor'])}</td>
                <td class='right'>{_pct(oImp['pis']['aliq'])}</td>
                <td class='right'>{_moeda(oImp['pis']['valor'])}</td>
                <td class='right'>{_pct(oImp['cofins']['aliq'])}</td>
                <td class='right'>{_moeda(oImp['cofins']['valor'])}</td>
                <td class='right'>{_moeda(oImp['ipi']['valor'])}</td>
            </tr>
        """)
    aLinhas.append("</tbody></table>")
    return "\n".join(aLinhas)


def _html_totais(oTotais: dict) -> str:
    """Gera bloco HTML de totais da nota."""
    return f"""
    <table class='tbl-info tbl-totais'>
        <tr><th>Produtos</th>      <td>{_moeda(oTotais.get('vProd',''))}</td>
            <th>Frete</th>         <td>{_moeda(oTotais.get('vFrete',''))}</td>
            <th>Desconto</th>      <td>{_moeda(oTotais.get('vDesc',''))}</td>
            <th><b>Total NF</b></th><td><b>{_moeda(oTotais.get('vNF',''))}</b></td>
        </tr>
        <tr><th>ICMS</th>          <td>{_moeda(oTotais.get('vICMS',''))}</td>
            <th>IPI</th>           <td>{_moeda(oTotais.get('vIPI',''))}</td>
            <th>PIS</th>           <td>{_moeda(oTotais.get('vPIS',''))}</td>
            <th>COFINS</th>        <td>{_moeda(oTotais.get('vCOFINS',''))}</td>
        </tr>
        <tr><th>ST</th>            <td>{_moeda(oTotais.get('vST',''))}</td>
            <th colspan="3">Total tributos (estimativa)</th>
            <td colspan="2"><b>{_moeda(oTotais.get('vTotTrib',''))}</b></td>
        </tr>
    </table>
    """


def _html_nota(oNota: dict, iIndice: int) -> str:
    """Gera a seção HTML completa de uma nota fiscal."""
    oR = oNota["resumo"]
    sTpNF = "Saída (1)" if oR.get("tpNF") == "1" else "Entrada (0)"
    sMod  = "NFC-e (65)" if oR.get("mod") == "65" else f"NF-e ({oR.get('mod','')})"

    return f"""
    <section class='nota' id='nota-{iIndice}'>
        <div class='nota-header'>
            <span class='nota-num'>NF {oR.get('numero','-')} | Série {oR.get('serie','-')}</span>
            <span class='nota-data'>{_formatar_data(oR.get('dhEmi',''))}</span>
            <span class='nota-tipo badge-{oR.get("tpNF","0")}'>{sTpNF} – {sMod}</span>
        </div>
        <div class='nota-subheader'>
            <span><b>Natureza da operação:</b> {oR.get('natOp','—')}</span>
            <span class='chave'>Chave: {oR.get('chave','—')}</span>
        </div>

        <div class='grid-2col'>
            {_html_participante(oNota.get('emissor', {}), 'Emissor')}
            {_html_participante(oNota.get('tomador', {}), 'Destinatário / Tomador')}
        </div>

        <h4>Itens da nota</h4>
        <div class='scroll-x'>
            {_html_itens(oNota.get('itens', []))}
        </div>

        <h4>Totais</h4>
        {_html_totais(oNota.get('totais', {}))}

        {"<h4>Observações</h4><p class='obs'>" + oNota.get('obs_cpl','') + "</p>" if oNota.get('obs_cpl') else ""}
        {"<h4>Observações fiscais</h4><p class='obs'>" + oNota.get('obs_fisco','') + "</p>" if oNota.get('obs_fisco') else ""}

        <p class='fonte-arquivo'>Arquivo: {oNota.get('arquivo','')}</p>
    </section>
    """


def _html_erro(sCaminho: str, sErro: str, iIndice: int) -> str:
    """Gera bloco HTML para um XML que falhou no processamento."""
    return f"""
    <section class='nota nota-erro' id='nota-erro-{iIndice}'>
        <div class='nota-header'>
            <span class='nota-num'>Erro ao processar #{iIndice}</span>
        </div>
        <p><b>Arquivo:</b> {sCaminho}</p>
        <p class='erro-msg'>{sErro}</p>
    </section>
    """


def _html_resumo_consolidado(aNotas: list, aErros: list) -> str:
    """Gera seção de resumo consolidado no topo do relatório."""
    fTotalNF    = 0.0
    fTotalICMS  = 0.0
    fTotalPIS   = 0.0
    fTotalCOFINS= 0.0
    fTotalIPI   = 0.0
    fTotalTrib  = 0.0
    iTotalItens = 0

    for oNota in aNotas:
        oT = oNota.get("totais", {})
        try: fTotalNF     += float(oT.get("vNF",     "0") or "0")
        except: pass
        try: fTotalICMS   += float(oT.get("vICMS",   "0") or "0")
        except: pass
        try: fTotalPIS    += float(oT.get("vPIS",    "0") or "0")
        except: pass
        try: fTotalCOFINS += float(oT.get("vCOFINS", "0") or "0")
        except: pass
        try: fTotalIPI    += float(oT.get("vIPI",    "0") or "0")
        except: pass
        try: fTotalTrib   += float(oT.get("vTotTrib","0") or "0")
        except: pass
        iTotalItens += len(oNota.get("itens", []))

    def _m(fV: float) -> str:
        return f"R$ {fV:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"""
    <section class='resumo-consolidado'>
        <h2>Resumo consolidado</h2>
        <div class='resumo-grid'>
            <div class='card'><span class='card-label'>Notas processadas</span>
                <span class='card-valor'>{len(aNotas)}</span></div>
            <div class='card card-erro'><span class='card-label'>Falhas</span>
                <span class='card-valor'>{len(aErros)}</span></div>
            <div class='card'><span class='card-label'>Total de itens</span>
                <span class='card-valor'>{iTotalItens}</span></div>
            <div class='card card-destaque'><span class='card-label'>Total NF (∑ vNF)</span>
                <span class='card-valor'>{_m(fTotalNF)}</span></div>
            <div class='card'><span class='card-label'>Total ICMS</span>
                <span class='card-valor'>{_m(fTotalICMS)}</span></div>
            <div class='card'><span class='card-label'>Total PIS</span>
                <span class='card-valor'>{_m(fTotalPIS)}</span></div>
            <div class='card'><span class='card-label'>Total COFINS</span>
                <span class='card-valor'>{_m(fTotalCOFINS)}</span></div>
            <div class='card'><span class='card-label'>Total IPI</span>
                <span class='card-valor'>{_m(fTotalIPI)}</span></div>
            <div class='card card-destaque'><span class='card-label'>Total tributos estimados</span>
                <span class='card-valor'>{_m(fTotalTrib)}</span></div>
        </div>
    </section>
    """


def _css() -> str:
    """Retorna o CSS do relatório."""
    return """
    :root {
        --cor-primaria: #1a5276;
        --cor-secundaria: #2980b9;
        --cor-acento: #e67e22;
        --cor-sucesso: #27ae60;
        --cor-erro: #c0392b;
        --cor-fundo: #f4f6f8;
        --cor-card: #ffffff;
        --cor-borda: #dde3ea;
        --fonte: 'Segoe UI', Arial, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: var(--fonte);
        background: var(--cor-fundo);
        color: #2c3e50;
        font-size: 13px;
        line-height: 1.5;
    }
    header {
        background: var(--cor-primaria);
        color: #fff;
        padding: 20px 32px;
    }
    header h1 { font-size: 22px; font-weight: 700; }
    header p  { font-size: 12px; opacity: .8; margin-top: 4px; }

    .container { max-width: 1400px; margin: 0 auto; padding: 24px 16px; }

    /* ── Resumo consolidado ──────────────────────────────────────────── */
    .resumo-consolidado {
        background: var(--cor-card);
        border: 1px solid var(--cor-borda);
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 28px;
    }
    .resumo-consolidado h2 {
        font-size: 16px;
        color: var(--cor-primaria);
        margin-bottom: 16px;
        border-bottom: 2px solid var(--cor-secundaria);
        padding-bottom: 6px;
    }
    .resumo-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
    }
    .card {
        background: var(--cor-fundo);
        border: 1px solid var(--cor-borda);
        border-radius: 6px;
        padding: 12px 16px;
        min-width: 150px;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .card-label { font-size: 11px; color: #7f8c8d; text-transform: uppercase; }
    .card-valor { font-size: 18px; font-weight: 700; color: var(--cor-primaria); }
    .card-destaque { border-left: 4px solid var(--cor-acento); }
    .card-destaque .card-valor { color: var(--cor-acento); }
    .card-erro { border-left: 4px solid var(--cor-erro); }
    .card-erro .card-valor { color: var(--cor-erro); }

    /* ── Seção de nota ───────────────────────────────────────────────── */
    .nota {
        background: var(--cor-card);
        border: 1px solid var(--cor-borda);
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 24px;
    }
    .nota-header {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 8px;
        padding-bottom: 10px;
        border-bottom: 2px solid var(--cor-secundaria);
    }
    .nota-num  { font-size: 16px; font-weight: 700; color: var(--cor-primaria); }
    .nota-data { font-size: 12px; color: #7f8c8d; }
    .nota-tipo { font-size: 11px; padding: 3px 8px; border-radius: 12px;
                 background: #eaf4fb; color: var(--cor-secundaria); font-weight: 600; }
    .badge-0   { background: #eaf7ee; color: var(--cor-sucesso); }
    .nota-subheader {
        display: flex;
        gap: 24px;
        flex-wrap: wrap;
        font-size: 12px;
        margin-bottom: 16px;
        color: #555;
    }
    .chave { font-family: monospace; font-size: 11px; color: #95a5a6; }

    .nota-erro { border-left: 4px solid var(--cor-erro); }
    .nota-erro .nota-num { color: var(--cor-erro); }
    .erro-msg { color: var(--cor-erro); font-family: monospace;
                background: #fdf2f2; padding: 8px; border-radius: 4px; margin-top: 6px; }

    /* ── Grid 2 colunas ──────────────────────────────────────────────── */
    .grid-2col {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 20px;
    }
    @media (max-width: 768px) { .grid-2col { grid-template-columns: 1fr; } }

    /* ── Tabelas de info ─────────────────────────────────────────────── */
    h4 { font-size: 13px; color: var(--cor-primaria); margin: 14px 0 8px;
         text-transform: uppercase; letter-spacing: .5px; }
    .tbl-info { width: 100%; border-collapse: collapse; font-size: 12px; }
    .tbl-info th {
        text-align: left; padding: 5px 10px;
        width: 130px; color: #7f8c8d; font-weight: 600;
    }
    .tbl-info td { padding: 5px 10px; }
    .tbl-info tr:nth-child(even) { background: var(--cor-fundo); }

    .tbl-totais th { width: auto; white-space: nowrap; }
    .tbl-totais td { white-space: nowrap; }

    /* ── Tabela de itens ─────────────────────────────────────────────── */
    .scroll-x { overflow-x: auto; margin-bottom: 16px; }
    .tbl-itens { border-collapse: collapse; width: 100%; min-width: 900px;
                  font-size: 11.5px; }
    .tbl-itens thead tr { background: var(--cor-primaria); color: #fff; }
    .tbl-itens th { padding: 7px 8px; text-align: center; font-weight: 600;
                    white-space: nowrap; }
    .tbl-itens td { padding: 5px 8px; border-bottom: 1px solid var(--cor-borda); }
    .tbl-itens tbody tr:hover { background: #eaf4fb; }
    .center { text-align: center; }
    .right  { text-align: right;  }

    /* ── Observações ─────────────────────────────────────────────────── */
    .obs {
        font-size: 11.5px; color: #555;
        background: #fffbf0; border-left: 3px solid var(--cor-acento);
        padding: 8px 12px; border-radius: 4px; margin-bottom: 10px;
    }
    .fonte-arquivo { font-size: 10.5px; color: #b0bec5; margin-top: 12px; }
    .vazio { color: #aaa; font-style: italic; }

    /* ── Índice de notas ─────────────────────────────────────────────── */
    .indice {
        background: var(--cor-card); border: 1px solid var(--cor-borda);
        border-radius: 8px; padding: 16px 24px; margin-bottom: 24px;
    }
    .indice h2 { font-size: 14px; color: var(--cor-primaria);
                 margin-bottom: 10px; }
    .indice ul { list-style: none; display: flex; flex-wrap: wrap; gap: 8px; }
    .indice li a {
        display: inline-block; padding: 4px 10px; border-radius: 14px;
        background: #eaf4fb; color: var(--cor-secundaria);
        font-size: 12px; text-decoration: none; font-weight: 600;
    }
    .indice li a:hover { background: var(--cor-secundaria); color: #fff; }
    .indice li.erro a  { background: #fdf2f2; color: var(--cor-erro); }

    footer {
        text-align: center; padding: 20px;
        font-size: 11px; color: #aaa;
        border-top: 1px solid var(--cor-borda);
        margin-top: 32px;
    }
    """


def _gerar_html(aNotas: list, aErros: list, sArquivoLista: str) -> str:
    """
    Monta o HTML completo do relatório.

    Args:
        aNotas:         Lista de dicionários de notas processadas com sucesso.
        aErros:         Lista de dicionários {'caminho', 'erro'} de falhas.
        sArquivoLista:  Caminho do arquivo .txt usado como entrada.

    Returns:
        String com o HTML completo.
    """
    sDtGeracao = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    # ── Índice de navegação ───────────────────────────────────────────────────
    aItensIndice = []
    for i, oNota in enumerate(aNotas, 1):
        oR = oNota["resumo"]
        sLabel = f"NF {oR.get('numero','-')}"
        aItensIndice.append(f'<li><a href="#nota-{i}">{sLabel}</a></li>')
    for i, oErr in enumerate(aErros, 1):
        sLabel = Path(oErr["caminho"]).name[:30]
        aItensIndice.append(f'<li class="erro"><a href="#nota-erro-{i}">⚠ {sLabel}</a></li>')

    sIndice = f"""
    <div class='indice'>
        <h2>Índice das notas ({len(aNotas)} processadas / {len(aErros)} com erro)</h2>
        <ul>{''.join(aItensIndice)}</ul>
    </div>
    """ if (aNotas or aErros) else ""

    # ── Seções das notas ──────────────────────────────────────────────────────
    aSecoes = []
    for i, oNota in enumerate(aNotas, 1):
        aSecoes.append(_html_nota(oNota, i))
    for i, oErr in enumerate(aErros, 1):
        aSecoes.append(_html_erro(oErr["caminho"], oErr["erro"], i))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório NF-e – {sDtGeracao}</title>
    <style>{_css()}</style>
</head>
<body>
    <header>
        <h1>Relatório de Notas Fiscais Eletrônicas</h1>
        <p>Gerado em {sDtGeracao} | Arquivo de entrada: {sArquivoLista}</p>
    </header>
    <div class='container'>
        {_html_resumo_consolidado(aNotas, aErros)}
        {sIndice}
        {''.join(aSecoes)}
    </div>
    <footer>Relatório gerado automaticamente &ndash; Copyright &copy; 2026 VIA. Desenvolvido por VIA.</footer>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Leitura da lista de XMLs
# ══════════════════════════════════════════════════════════════════════════════

def _ler_lista_xmls(sArquivoTxt: str) -> list:
    """
    Lê o arquivo .txt e retorna lista de caminhos, ignorando linhas vazias e comentários.

    Args:
        sArquivoTxt: Caminho para o arquivo .txt.

    Returns:
        Lista de strings com os caminhos/URLs de cada XML.

    Raises:
        FileNotFoundError: Se o arquivo .txt não existir.
    """
    oCaminho = Path(sArquivoTxt)
    if not oCaminho.exists():
        raise FileNotFoundError(f"Arquivo de lista não encontrado: {sArquivoTxt}")

    aCaminhos = []
    with open(str(oCaminho), "r", encoding="utf-8-sig") as oArq:
        for sLinha in oArq:
            sLinha = sLinha.strip()
            # Ignora linhas vazias e comentários (# ou //)
            if not sLinha or sLinha.startswith("#") or sLinha.startswith("//"):
                continue
            aCaminhos.append(sLinha)

    return aCaminhos


# ══════════════════════════════════════════════════════════════════════════════
# Execução principal
# ══════════════════════════════════════════════════════════════════════════════

def _solicitar_arquivo_lista() -> str:
    """Solicita interativamente o caminho do arquivo .txt."""
    print("\n" + "=" * 60)
    print("  Relatório NF-e HTML – Processador de Notas Fiscais")
    print("=" * 60)
    print("\nNenhum arquivo fornecido via argumento de linha de comando.")
    sCaminho = input("Informe o caminho do arquivo .txt com a lista de XMLs: ").strip()
    return sCaminho


def main() -> None:
    """Ponto de entrada principal do script."""

    # ── Determina o arquivo .txt de entrada ───────────────────────────────────
    if len(sys.argv) >= 2:
        sArquivoTxt = sys.argv[1]
    else:
        sArquivoTxt = _solicitar_arquivo_lista()

    if not sArquivoTxt:
        print("[ERRO] Nenhum arquivo informado. Encerrando.")
        sys.exit(1)

    # ── Lê a lista de caminhos ────────────────────────────────────────────────
    try:
        aCaminhos = _ler_lista_xmls(sArquivoTxt)
    except FileNotFoundError as oEx:
        print(f"[ERRO] {oEx}")
        sys.exit(1)

    if not aCaminhos:
        print("[AVISO] O arquivo .txt está vazio ou não contém caminhos válidos.")
        sys.exit(0)

    print(f"\n{'=' * 60}")
    print(f"  {len(aCaminhos)} arquivo(s) XML encontrado(s) na lista.")
    print(f"{'=' * 60}\n")

    # ── Processa cada XML ─────────────────────────────────────────────────────
    aNotas: list = []
    aErros: list = []

    for iIdx, sCaminho in enumerate(aCaminhos, 1):
        sCaminhoNorm = sCaminho.strip()
        sNomeArquivo = Path(sCaminhoNorm).name

        try:
            print(f"[{iIdx:>4}/{len(aCaminhos)}] Processando: {sNomeArquivo}... ", end="", flush=True)
            oNota = _extrair_nota(sCaminhoNorm)
            aNotas.append(oNota)
            sNumNF = oNota["resumo"].get("numero", "?")
            print(f"OK  (NF {sNumNF})")

        except FileNotFoundError as oEx:
            sErro = str(oEx)
            print(f"FALHA  [{sErro}]")
            aErros.append({"caminho": sCaminhoNorm, "erro": sErro})

        except ET.ParseError as oEx:
            sErro = f"XML inválido: {oEx}"
            print(f"FALHA  [{sErro}]")
            aErros.append({"caminho": sCaminhoNorm, "erro": sErro})

        except Exception as oEx:
            sErro = f"{type(oEx).__name__}: {oEx}"
            print(f"FALHA  [{sErro}]")
            aErros.append({"caminho": sCaminhoNorm, "erro": sErro})

    # ── Gera HTML ─────────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Sucesso: {len(aNotas)} | Falha: {len(aErros)}")
    print(f"{'─' * 60}")

    sHtml = _gerar_html(aNotas, aErros, sArquivoTxt)

    # Nome do arquivo de saída com timestamp (caminho absoluto)
    sDirSaida = Path(sArquivoTxt).resolve().parent
    sDtStamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    sSaida    = str(sDirSaida / f"relatorio_nfe_{sDtStamp}.html")

    with open(sSaida, "w", encoding="utf-8") as oArq:
        oArq.write(sHtml)

    print(f"\n[OK] Relatório gerado: {sSaida}")

    # ── Abre no navegador ─────────────────────────────────────────────────────
    try:
        webbrowser.open(Path(sSaida).as_uri())
        print("[OK] Relatório aberto no navegador padrão.")
    except Exception as oEx:
        print(f"[AVISO] Não foi possível abrir o navegador automaticamente: {oEx}")
        print(f"        Abra manualmente: {sSaida}")


if __name__ == "__main__":
    main()
