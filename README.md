# G500_database

This code was used to produce the data and results of the following pieces of scientific literature.

| Description | Link|
| -------| ----- |
| Research article in Nature Communications  | https://doi.org/10.1038/s41467-023-38989-2  |
| Master thesis at TU Delft  | http://resolver.tudelft.nl/uuid:4088c251-9128-4132-99a5-69b336c34478 |
| FAIR Dataset | https://doi.org/10.4121/16616965 |

If you use this code or its methods in your study, please make sure to cite at least one of the resources above.

## Scrapping, parsing and database creation
1. G500 data scrapping
  - fortune_g500.py: obtains Global G500 data from Fortune's website. Not maintaned.
  - g500_scraper.py: supporting module
  - database_operations.py: supporting module
2. HTML CDP questionnaire parser
  - company_operations.py: main script for parsing CDP company data to an Excel file with validation formulas. To run, specify a company name (case sensitive) and filepaths of 5 CDP questionnaire HTML files (order does not matter). Make sure a duplicate file does not exist already in the data/companies folder. Move validated files to the "collected" folder
  - cdp_parser.py: supporting module
3. Pandas database creation (.csv)
  - company_excel_to_pandas.py: will read through all "collected" company files, as well as G500/RE100/SBTi data to create disaggregated databases in the data/ folder.
  
## ICI Database
1. Data manipulation:
  - g500.py: module for parent class with access to all G500 company data. Establishes basic functionality.
  - ici.py: wrapper for all initiatives. Inherits g500
  - sbti.py: holds SBTi members exclusively and has sbti-specific functionality. Inherits ici
  - re100.py: holds RE100 members exclusively and has re100-specific functionality. Inherits ici
2. Plotting:
  - ncc_plots.py: plotting used in published papers.
  - combined_plots: depreciated plots used in the thesis (http://resolver.tudelft.nl/uuid:4088c251-9128-4132-99a5-69b336c34478)
3. Other:
  - ipcc_scenarios.py: to assist in handling IIASA scenario results
  - unep.py: handles UNEP gap report (2019) data for some plots. Deppreciated.
  - nat_earth.py: to assist in handling Natural Earth country data. Deppreciated.
