import pandas as pd
import numpy as np

PATH = "/home/ivan/Documents/GitHub/G500_database/data/other/"
RENEWABLE = ["Hydro (% electricity)", "Solar (% electricity)", "Wind (% electricity)",
             "Other renewables (% electricity)"]


def get_ipcc_re_electricity_benchmark(pathway_name, start_year=2010, end_year=2050):
    ipcc_df = pd.read_csv(PATH+"ssp_renewable.csv", index_col=[0, 1])
    ipcc_df.columns = ipcc_df.columns.astype(int)
    pathway = ipcc_df.loc[pathway_name]

    years = np.arange(start_year, end_year+1, 1)
    mini = np.interp(years, pathway.columns, pathway.loc['min'])
    maxi = np.interp(years, pathway.columns, pathway.loc['max'])

    return years, mini, maxi


def get_scenario_df(filename, ssp, region, models):
    """
    Fetches data from IAMC databases obtained from the IIASA website.
    :param filename: "iamc_ssp_emissions.csv"
    :param ssp: SSP1-19, SSP2-Baseline, etc.
    :param region: World, R5OECD90+EU, etc.
    :param models: AIM/CGE 2.0, GCAM 4.2, etc.
    :return: dataframe
    """
    df = pd.read_csv(PATH + filename)
    df = df[(df.Scenario == ssp) & (df.Region == region)]
    if models:
        df = df[df.Model.isin(models)]
    return df


def min_max_linearization(df, year_start, year_end):
    """
    Takes a scenario dataframe and simplifies it to only min values, max values for the specified years
    :param df: scenario dataframe from get_scenario_df
    :param year_start: 2010 to 2100
    :param year_end: 2010 to 2100
    :return:
    """
    df = df.loc[:, "2010":]
    years = np.linspace(2010, 2100, 2100 - 2010 + 1)
    xp = df.columns.values.astype(int)
    scenario = pd.DataFrame(index=years)
    scenario['max'] = np.interp(years, xp, pd.DataFrame.max(df).to_list())
    scenario['min'] = np.interp(years, xp, pd.DataFrame.min(df).to_list())
    return scenario.T.loc[:, year_start:year_end]


def get_emissions_scenario(ssp, region, models=None, year_start=2020, year_end=2030):
    """
    Wrapper for emission database
    :param ssp:
    :param region:
    :param models:
    :param year_start:
    :param year_end:
    :return:
    """
    df = get_scenario_df("iamc_ssp_emissions.csv", ssp, region, models)
    scenario = min_max_linearization(df, year_start, year_end)

    return scenario


def get_electricity_scenario_ratio(ssp, region, models=None, year_start=2020, year_end=2030):
    """
    Wrapper for electricity ratios
    :param ssp:
    :param region:
    :param models:
    :param year_start:
    :param year_end:
    :return:
    """
    df = get_scenario_df("iamc_ssp_electricity.csv", ssp, region, models)
    ratios = pd.DataFrame(index=df.Model.unique(), columns=df.columns)
    for index in ratios.index:
        biomass = 'Secondary Energy|Electricity|Biomass'
        non_biomass = 'Secondary Energy|Electricity|Non-Biomass Renewables'
        electricity = 'Secondary Energy|Electricity'
        renewables = df[(df.Model == index) & ((df.Variable == biomass) | (df.Variable == non_biomass))].sum()
        ratio = df[(df.Model == index) & (df.Variable == electricity)].sum()
        ratio["2010":] = renewables["2010":] / ratio["2010":]
        ratios.loc[index] = ratio

    scenario = min_max_linearization(ratios, year_start, year_end)
    return scenario

