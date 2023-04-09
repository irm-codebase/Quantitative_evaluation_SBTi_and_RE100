import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz

import database_operations
# import g500_scrapers

PATH = "/home/ivan/Documents/GitHub/G500_database/data/"
TEMPLATE_PATH = "/home/ivan/Documents/GitHub/G500_database/templates"


def sort_fortune_g500(path, n_attributes=2):
    """
    Simple file reader that turns text taken from the Forbes G500 into a dictionary.
    The company's rank and name must always be the first and second attributes.
    Example:
    1
    Walmart
    :param path: /user/you/file.txt
    :param n_attributes: number of attributes per company (rank, name, revenue...)
    :return: dict
    """
    with open(path, 'r') as file:
        elements = list(file)
        # Remove line breaks
        elements = [str.rstrip(element) for element in elements]
        companies = {}
        index = 0
        for n, element in enumerate(elements):
            if n % n_attributes == 0:
                index = int(element)
                companies[index] = {}
                companies[index]["rank 2020"] = int(element)
            elif n % n_attributes == 1:
                companies[index]["company"] = element
            else:
                pass
        return companies


def get_g500_de_jong_intensity(g500_path=PATH+"/G500_sector.csv",
                               de_jong_path=PATH+"/other/deJongSectorIntensities.ods", new_file=True, out_path=PATH):
    """
    Creates a new g500 with the predicted carbon intensity added to it. Useful for setting the info collection order.
    IMPORTANT: de Jong's indexes are for a company's TURNOVER. Fortune gives REVENUE.
    PREREQUISITES: G500 database, pruned and with sectors matching the deJongDatabase.
    :param g500_path: location of the g500 database produced by combine_g500_sectors().
    :param de_jong_path: database with de Jong's sector indexes and the G500 industry they match.
    :param new_file: if True, create a new file in out_path. Otherwise, overwrite g500_path.
    :param out_path: location of the output file
    :return:
    """
    g500 = pd.read_csv(g500_path, index_col=0, header=[0])
    jong = pd.read_excel(de_jong_path)

    # Build a dictionary of industries and their intensity (tCO2e/Million USD)
    industry_intensity_dict = {}
    intensity_col = 'Emission intensity (tCO2e/Million USD Turnover)'
    industry_col = 'G500 Industry'
    for i in jong.index:
        industries = jong.loc[i, industry_col]
        if not pd.isna(industries):
            industries = industries.split(';')
            for industry in industries:
                industry_intensity_dict[industry] = jong.loc[i, intensity_col]

    # Add de Jong Intensity to the G500 database
    industry_col = 'industry'
    revenue_col = 'revenues ($M)'
    predictions = pd.Series(data='float64', index=g500.index)
    for company in g500.index:
        industry = g500.loc[company, industry_col]
        revenue = g500.loc[company, revenue_col].replace('$', '')
        revenue = int(revenue.replace(',', ''))
        try:
            intensity = industry_intensity_dict[industry]
            predictions[company] = revenue * intensity
        except KeyError:
            print("Could not find", industry, "in de Jong dictionary")

    # Rearrange and create output file
    g500['de jong (tCO2e)'] = predictions
    g500 = database_operations.move_column(g500, 'de jong (tCO2e)', 'ceo')
    if new_file:
        g500.to_csv(out_path + "G500_deJong.csv")
    else:
        g500.to_csv(g500_path)


def fuzzy_g500_vs_initiatives(g500_path=PATH+"/G500_sector.csv", re100_path=PATH+"/other/RE100.ods",
                              sbti_path=PATH+"/other/SBTi23022020.csv",
                              natural_path=PATH+"/other/naturalCapitalG500.ods", out_path=PATH):
    """
    Fuzzy string matching comparison between the G500 database and the RE100 database.
    Outputs a csv file for review: G500 name | RE100 name | Member? (yes/no)
    YOU MUST CHECK THIS OUTPUT FILE AS FUZZY MATCHING IS NOT 100% TRUST WORTHY
    :param str g500_path: path to the G500 database
    :param str re100_path: path to the RE100 database (obtained from the RE100 website)
    :param str sbti_path: path to the SBTi database (downloaded from the SBTi website)
    :param str natural_path: path to the Natural Capital database (obtained from a website)
    :param str out_path: Path were the new file(s) will be created
    :return:
    """
    # Companies that cause trouble in the search. Only omitted if they are not in the initiatives for sure
    exceptions_g500 = ["Mitsubishi", "Deutsche Bank", 'Sumitomo']

    # Companies that cause false positives
    exceptions_re100 = ["Mitsui Fudosan ", "Sumitomo Forestry Group ", "Coca-Cola European Partners "]
    exceptions_sbti = ['ABP Food Group', "Siemens Gamesa Renewable Energy, S.A.", "MAS Holdings (Pvt) Ltd.",
                       'Hitachi Capital Corporation', 'FIRMENICH SA', 'Mintel Group Limited', 'Carbon Intelligence',
                       'Volvo Car Group', 'Delmar International Inc', 'Coca-Cola FEMSA', 'Coca Cola European Partners',
                       'Coca-Cola HBC AG', 'Swire Coca-Cola Limited']

    g500 = pd.read_csv(g500_path, index_col=0, header=[0])
    re100 = pd.read_excel(re100_path)
    sbti = pd.read_csv(sbti_path)
    natural = pd.read_excel(natural_path, index_col=0, header=[0, 1])

    # Get all the names of the companies
    g500_names = g500.index.to_list()
    re100_names = re100['name'].to_list()
    sbti_names = sbti['Company Name'].to_list()

    results_dict = {}
    # Fill in a dictionary with the fuzzy names of companies, accounting exceptions (which will be ignored)
    for g500_name in g500_names:
        fuzz_ratio_re100 = 0
        fuzz_name_re100 = np.nan
        fuzz_ratio_sbti = 0
        fuzz_name_sbti = np.nan
        if g500_name not in exceptions_g500:
            # Fill in RE100
            for re100_name in re100_names:
                if re100_name not in exceptions_re100:
                    tmp = fuzz.partial_ratio(g500_name, re100_name)
                    if tmp > fuzz_ratio_re100:
                        fuzz_ratio_re100 = tmp
                        fuzz_name_re100 = re100_name
            # Fill in SBTi
            for sbti_name in sbti_names:
                if sbti_name not in exceptions_sbti:
                    tmp = fuzz.partial_ratio(g500_name, sbti_name)
                    if tmp > fuzz_ratio_sbti:
                        fuzz_ratio_sbti = tmp
                        fuzz_name_sbti = sbti_name

        results_dict[g500_name] = [fuzz_name_re100, fuzz_ratio_re100]
        if fuzz_ratio_re100 >= 90:
            results_dict[g500_name].append('yes')
        else:
            results_dict[g500_name].append(np.nan)

        results_dict[g500_name].append(fuzz_name_sbti)
        results_dict[g500_name].append(fuzz_ratio_sbti)
        if fuzz_ratio_sbti >= 90:
            results_dict[g500_name].append('yes')
        else:
            results_dict[g500_name].append(np.nan)

    # Build a dataframe with the fuzzy search and values
    column_names = ['RE100 name', 'RE100 score', 'RE100 pass?', 'SBTi name', 'SBTi score', 'SBTi pass?']
    result_df = pd.DataFrame.from_dict(results_dict, orient='index', columns=column_names)
    # Get a dataframe of companies and their supposed membership from nature's database
    natural_membership_df = natural.loc[:, [['re100', 'goal'], ['sbti', 'target set or committed']]]
    natural_membership_df = database_operations.flatten_multi_columns(natural_membership_df)

    # Combine them and produce a document for review
    result_df = result_df.merge(natural_membership_df, left_index=True, right_index=True, how='left')
    result_df.to_csv(out_path+"fuzzy_initiative_validation.csv")


def get_initiative_data_from_fuzzy(g500_path=PATH+'G500_sector.csv', fuzzy_path=PATH+"fuzzy_initiative_validation.csv",
                                   re100_path=PATH+"/other/RE100.ods", sbti_path=PATH+"/other/SBTi23022020.csv",
                                   new_file=True, out_path=PATH):
    df_g500 = pd.read_csv(g500_path, index_col=0, header=[0])
    df_fuzzy = pd.read_csv(fuzzy_path, index_col=[0], header=[0])
    df_re100 = pd.read_excel(re100_path, index_col=[0])
    df_sbti = pd.read_csv(sbti_path, index_col=[0])

    re100_membership = df_fuzzy['RE100 validated']
    sbti_membership = df_fuzzy['SBTi validated']

    re100_commitment = pd.Series(index=df_g500.index, dtype='string')
    sbti_status = pd.Series(index=df_g500.index, dtype='string')
    sbti_target = pd.Series(index=df_g500.index, dtype='string')
    sbti_target_qualification = pd.Series(index=df_g500.index, dtype='string')
    for company in df_g500.index:
        if re100_membership[company] == 'yes':
            name = df_fuzzy.loc[company, 'RE100 name']
            re100_commitment[company] = df_re100.loc[name, 'commitment']
        if sbti_membership[company] == 'yes':
            name = df_fuzzy.loc[company, 'SBTi name']
            sbti_target_qualification[company] = df_sbti.loc[name, 'Target Qualification']
            sbti_status[company] = df_sbti.loc[name, 'Status']
            sbti_target[company] = df_sbti.loc[name, 'Target']

    df_g500 = database_operations.add_column(df_g500, re100_membership, 're100 member', 'ceo')
    df_g500 = database_operations.add_column(df_g500, re100_commitment, 're100 target', 'ceo')
    df_g500 = database_operations.add_column(df_g500, sbti_membership, 'sbti member', 'ceo')
    df_g500 = database_operations.add_column(df_g500, sbti_status, 'sbti status', 'ceo')
    df_g500 = database_operations.add_column(df_g500, sbti_target_qualification, 'sbti qualification', 'ceo')
    df_g500 = database_operations.add_column(df_g500, sbti_target, 'sbti target', 'ceo')

    if new_file:
        df_g500.to_csv(out_path + "G500_initiatives.csv")
    else:
        df_g500.to_csv(g500_path)


def init_company_index_and_rank(companies, input_csv, output_csv):
    """
    Old initialization of an empty database. Depreciated.
    :param dict companies: dictionary with company names and rank, ordered by rank
    :param str input_csv: path to the .csv file to be initialized
    :param str output_csv: path+name of the combined output csv file
    :return:
    """
    forbes_ds = pd.DataFrame.from_dict(companies, orient='index')
    my_ds = pd.read_csv(input_csv, index_col=0, header=[0, 1])
    my_ds.index = forbes_ds.loc[:, "company"]
    my_ds.to_csv(output_csv)


if __name__ == "__main__":
    # init_company_index_and_rank(G500, "init.csv", PATH+"output.csv")
    # g500_scrapers.get_g500_database()
    # fuzzy_g500_vs_initiatives() NEEDS TO BE VALIDATED AFTER GENERATION
    # get_g500_de_jong_intensity(new_file=False)
    # get_initiative_data_from_fuzzy()
    pass
