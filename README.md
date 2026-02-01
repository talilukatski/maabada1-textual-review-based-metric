# Text-Based Hotel Category Scoring Index

Our project introduces a new scoring index for hotel categories, based only on textual reviews.

---

## Project Notebook

The notebook `project_notebook.ipynb` contains the full end-to-end execution of the project and generates the file `tool_input.csv`.

To run the notebook, the Azure SAS token must be added in the sections marked with `"..."`.

The notebook is provided without outputs in order to preserve data confidentiality, as required by the assignment.  
If needed, we also have a version of the notebook with full outputs.

---

## Scraping

All scraping files are located under the `scraper` directory.

To run each scraper, all required details must first be filled in the sections marked with `"..."`, and hotel names and relevant details must be provided in `hotels_list`.

Each file can be executed using:
python -m run scraper/file.py  
where `file` is one of the files in the directory.

---

## Interface

The interface is implemented using Streamlit and is located in the `interface` directory.

To run the interface, the following files must be added to the directory from Azure Storage (`itay_asaf_antal`):
- `tool_input.csv`
- `scraped_booking_real_scores.csv`

Dependencies are installed using:
python -m pip install -r requirements.txt

The interface is run using:
python -m streamlit run main.py
