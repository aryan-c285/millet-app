# Millet Match - Streamlit demo (rebuilt mapping)

Pick familiar dishes + health conditions -> millet alternatives, the ingredient
each millet replaces, and whether the swap helps the conditions (per-100 g).

## Files
- app.py                              Streamlit interface
- millet_engine.py                    scoring engine (reads the two data files)
- Millet_Replacement_Mapping_REBUILD.xlsx   the rebuilt replacement mapping
- Final Nutrition per 100g - Full Dataset.csv   per-100 g nutrition table

Keep all four in the same folder.

## Run
    pip install -r requirements.txt
    python -m streamlit run app.py

Then open the URL it prints (usually http://localhost:8501).

## Notes
- Conditions are scored on energy, carbohydrate, protein, fat and fibre.
- When conditions disagree on a nutrient (e.g. kidney wants protein down,
  osteoporosis wants it up) the app warns and shows the best trade-off.
- Confidence chip (High/Medium/Low) reflects how specifically the millet dish
  matches its mapped original; it is the review tier from the mapping workbook.
"# millet-app" 
