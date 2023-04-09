import pandas as pd
from g500 import G500
from g500 import PlotterG500
PATH = "/home/ivan/Documents/GitHub/G500_database/data/"


class ICI(G500):
    """
    Generic wrapper class for all ICIs.
    Standardizes non-member removal, applying it to all datasets.
    """
    def __init__(self, name):
        super().__init__(initialize=False)
        # Get SBTi database
        if name == 'RE100':
            ici_file = 'G500_re100.csv'
        elif name == 'SBTi':
            ici_file = 'G500_sbti.csv'
        else:
            raise ValueError("Invalid ICI given")

        ici = pd.read_csv(PATH + ici_file, index_col=0, header=[0])
        self.ici = ici[ici.member == 'yes'].copy()
        index = self.ici.index.to_list()

        # Remove all non-member companies using the ICI document as basis
        self.central = self.central.loc[index, :]
        self.energy = self.energy.loc[index, :]
        self.emissions = self.emissions.loc[index, :]
        self.s2mb = self.s2mb.loc[index, :]

        self.initialize()


class PlotterICI(PlotterG500):
    """
    Generic wrapper for ICI plotter classes.
    """
    def __init__(self):
        super(PlotterICI, self).__init__(init_data=False)