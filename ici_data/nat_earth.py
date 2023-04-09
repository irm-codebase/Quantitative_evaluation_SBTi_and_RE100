import pandas as pd

PATH = "/home/ivan/Documents/GitHub/G500_database/data/other/natural_earth.csv"


class NaturalEarth:
    def __init__(self):
        self.db = pd.read_csv(PATH)

    def get_db_country_to_un_region(self):
        return pd.Series(self.db['REGION_UN'].to_list(), index=self.db['ADMIN'])

    def get_db_country_to_wb_region(self):
        world = pd.Series(self.db['REGION_WB'].to_list(), index=self.db['ADMIN'])
        index = world.index
        index = [w.replace('United Kingdom', 'U.K.') for w in index]
        index = [w.replace('United States of America', 'U.S.') for w in index]
        world.index = index

        return pd.Series(self.db['REGION_WB'].to_list(), index=self.db['ADMIN'])