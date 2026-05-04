# ubc-mds-project

Repository for the UBC MDS DSCI 591 Group 8 Capstone Project in partnership with Beaty Biodiversity Museum

---

## Executive Summary

Taxonomy, including species names and ranks, is constantly changing with the advent of new scientific methods. Curators at the Beaty Biodiversity Museum have to keep track of all of these changes in order to keep the collections current, but finding and evaluating information can be time consuming. This web app synthesizes current information online regarding species name synonyms and taxonomy and provides it to curators, who can then decide which designation they'd like to incorporate into the museum's database.

---

## Background & Context

The [Beaty Biodiversity Museum](https://beatymuseum.ubc.ca/) at the University of British Columbia houses one of Canada's largest natural history collections. Keeping taxonomic records accurate is an ongoing challenge, as consensus on species names, synonyms, and classification shifts regularly with research and new scientific methods.

This project was developed as part of the UBC Master of Data Science (MDS) DSCI 591 Capstone Program (2025–2026), in partnership with the museum's informatics team.

---

## Project Structure

## Project Structure

```
ubc-mds-project/
├── app/
│   └── prototype.py          # Streamlit app entry point
├── deprecated/
│   └── AntWeb.py
├── reports/
│   ├── planned_reports/
│   │   └── inat-api-test.ipynb
│   └── proposal.ipynb
├── scripts/APIs/
│   ├── planned_scripts/
│   │   └── iNat.py
│   ├── call_APIs.py
│   ├── COL.py                # Catalogue of Life
│   ├── GBIF.py
│   ├── GenBank.py
│   └── MushroomObs.py
├── tests/
├── .env.example              # Template for environment variables
├── .gitignore
├── environment.yml           # Conda environment
├── LICENSE
└── README.md
```

---

## Environment Setup

### 1. Create the Conda environment

From the root of the repository, run:

```bash
conda env create -f environment.yml
```

### 2. Activate the environment

```bash
conda activate mds-project
```

### 3. Set up environment variables

This project uses a `.env` file for secrets and credentials:

1. Copy the example file, `.env.example`, into a file named `.env`:

```bash
   cp .env.example .env
```

1. Open `.env` and replace the placeholder values with your own (see comments in the file for details).
2. Never commit `.env` — it is listed in `.gitignore`.

---

## Running the App

With the environment active, launch the Streamlit app from the root of the repository:

```bash
streamlit run app/prototype.py
```

Then open your browser to `http://localhost:8501`.

---

## Usage Guide

The app is designed to help museum curators quickly look up and evaluate current taxonomic information.

1. **Search** — Enter a species name in the search bar.
2. **Review** — The app retrieves current synonyms and taxonomic status from different data sources, e.g. GBIF, Catalogue of Life.
3. **Decide** — Choose the designation you'd like to incorporate (no app activity corresponds)

[Expand this section with screenshots or a short GIF once the app is more complete.]

---

## Contributors

| Name | GitHub |
|------|--------|
| [Wendy Frankel] | [@handle](https://github.com/handle) |
| [Molly Kessler] | [@handle](https://github.com/kessler24) |
| [William Song] | [@handle](https://github.com/wendyf55) |
| [Johnson Chuang] | [@handle](https://github.com/stoyq) |

---

## Citations

GBIF:
'Tools returning results directly from the GBIF search API (e.g. spocc, dismo and the occ_data() and occ_search() functions of rgbif) will not assign single DOIs for data downloaded. It is up to the user to identify dataset publishers and properly acknowledge each of them when citing the data.

For data obtained via occurrence search API-based tools, we recommend using a derived dataset as an easy way of obtaining a DOI for citing the data. The rOpenSci documentation site provides instructions on how to cite GBIF-mediated data in rgbif.' **something to do before we make this repository public!**

Catalogue of Life:
Bánki, O., Roskov, Y., Döring, M., Ower, G., Hernández Robles, D. R., Plata Corredor, C. A., Stjernegaard Jeppesen, T., Örn, A., Pape, T., Hobern, D., Garnett, S., Little, H., DeWalt, R. E., Miller, J., Orrell, T., Aalbu, R., Abbott, J., Abreu, C., Acero P, A., et al. (2026). Catalogue of Life (2026-04-18 XR). Catalogue of Life Foundation, Amsterdam, Netherlands. <https://doi.org/10.48580/dgxjw>

Index Fungorum:
IndexFungorum (2025). Published on the Internet <http://www.indexfungorum.org>, The Royal Botanic Gardens, Kew. [Retrieved 1 May 2026].

NCBI (Basically, GenBank):
Entrez® Programming Utilities Help [Internet]. Bethesda (MD): National Center for Biotechnology Information (US); 2010-. Available from: <https://www.ncbi.nlm.nih.gov/books/NBK25501/>

Mushroom Observer:
Wilson, N., Hollinger, J., et al. 2006-present. Mushroom Observer. <https://mushroomobserver.org>
---

## License

This project is licensed under the [MIT License](LICENSE).
