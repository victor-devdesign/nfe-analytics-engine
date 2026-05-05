# NFe Analytics Engine

Sistema para processar arquivos XML de Notas Fiscais Eletrônicas (NF-e) e gerar relatórios HTML consolidados de forma visual e organizada.

## 📋 Descrição

Este projeto extrai informações de múltiplos XMLs de NF-e e consolida os dados em um relatório HTML único, facilitando a análise e visualização de notas fiscais. O sistema processa informações de emitente, destinatário, produtos, impostos e valores.

## 🚀 Funcionalidades

- **Processamento em lote**: Processa múltiplos XMLs de uma só vez
- **Interface gráfica intuitiva**: Selecione arquivos facilmente com checkboxes
- **Filtros inteligentes**: Filtre por nome ou tipo de arquivo (AUTORIZADO, CANCELADO, etc.)
- **Relatório HTML**: Visualização organizada com tabelas formatadas
- **Formatação automática**: CNPJs, CPFs, valores monetários e datas formatados
- **Abertura automática**: O relatório abre automaticamente no navegador após geração

## 📦 Requisitos

- Python 3.8 ou superior
- Tkinter (geralmente já incluído no Python)
- Bibliotecas padrão: `xml.etree.ElementTree`, `webbrowser`, `pathlib`

## 💻 Como Usar

### Opção 1: Interface Gráfica (Recomendado)

Execute o seletor visual de arquivos:

```bash
python seletor_nfe.py
```

1. Clique em **"📁 Navegar pasta"** para selecionar uma pasta com XMLs
2. Ou clique em **"📄 Selecionar arquivos"** para escolher XMLs específicos
3. Use os filtros para encontrar os arquivos desejados
4. Marque os XMLs que deseja processar
5. Clique em **"Gerar Relatório HTML"**
6. O relatório será aberto automaticamente no navegador

### Opção 2: Linha de Comando

Crie um arquivo `.txt` contendo os caminhos dos XMLs (um por linha):

```
C:\notas\nota1.xml
C:\notas\nota2.xml
C:\notas\nota3.xml
```

Execute o processador:

```bash
python relatorio_nfe_html.py lista_xmls.txt
```

Ou execute sem argumentos para ser solicitado interativamente:

```bash
python relatorio_nfe_html.py
```

## 📊 Dados Extraídos

O relatório HTML inclui:

- **Dados gerais**: Número, série, data de emissão, valor total
- **Emitente**: CNPJ/CPF, razão social, endereço, telefone, e-mail
- **Destinatário**: CNPJ/CPF, razão social, endereço, telefone, e-mail
- **Produtos/Serviços**: Código, descrição, NCM, CFOP, quantidade, valores
- **Impostos**: ICMS, PIS, COFINS, IPI (alíquotas e valores)
- **Totais**: Base de cálculo, impostos, desconto, frete, valor total

## 📁 Estrutura do Projeto

```
nfe-analytics-engine/
├── seletor_nfe.py          # Interface gráfica para seleção de XMLs
├── relatorio_nfe_html.py   # Motor de processamento e geração HTML
├── README.md               # Este arquivo
└── LICENSE                 # Licença do projeto
```

## 🎨 Tipos de XML Suportados

O sistema reconhece e filtra diferentes tipos de XMLs de NF-e:

- ✅ AUTORIZADO
- ✅ NFCe AUTORIZADO
- ✅ CANCELADO
- ✅ CORRECAO
- ✅ GERADO
- ✅ ASSINADO
- ✅ INUTILIZADO

## 🔧 Namespace

O sistema trabalha com o namespace padrão das NF-e:
```
http://www.portalfiscal.inf.br/nfe
```

## 📝 Exemplo de Saída

O relatório HTML gerado contém:

- Cabeçalho com total de notas processadas
- Tabela consolidada com todas as notas
- Detalhes expandidos de cada nota (itens, impostos, participantes)
- Formatação responsiva e visual agradável
- Totalizadores e estatísticas

## 👤 Autor

VIA

## 📅 Data

Maio de 2026

---

**Dica**: Para melhor experiência, utilize a interface gráfica (`seletor_nfe.py`). Ela oferece filtros, seleção visual e feedback de progresso em tempo real!
