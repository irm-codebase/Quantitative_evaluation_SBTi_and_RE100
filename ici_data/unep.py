import numpy as np
import pandas as pd

# Used to compare trends to UNEP reports (2020).
# NOT USED FOR THE NCC PAPER.

YEARS = np.arange(2019, 2030+1)
GLOBAL_L = 53.6  # UNEP 2020 Ch3
GLOBAL_H = 56.7  # UNEP 2020 Ch2 with LUC of Ch3


def build_ghg(start, end, name):
    return pd.Series(data=np.interp(YEARS, [YEARS.min(), YEARS.max()], [start, end]), index=YEARS, name=name)


def normalize(df, year, norm=1):
    avg = 0
    for name in df.index:
        avg += df.loc[name, year]
    df = df / (avg/len(df))
    return df * norm


def get_current_policies_ghg():
    ghg = pd.DataFrame()
    ghg = ghg.append(build_ghg(GLOBAL_L, 56, 'low'))
    ghg = ghg.append(build_ghg(GLOBAL_H, 65, 'high'))
    return ghg


def get_1_5_ghg():
    ghg = pd.DataFrame()
    ghg = ghg.append(build_ghg(GLOBAL_L, 22, 'low'))
    ghg = ghg.append(build_ghg(GLOBAL_H, 31, 'high'))
    return ghg


def get_2_ghg():
    ghg = pd.DataFrame()
    ghg = ghg.append(build_ghg(GLOBAL_L, 39, 'low'))
    ghg = ghg.append(build_ghg(GLOBAL_H, 46, 'high'))
    return ghg
