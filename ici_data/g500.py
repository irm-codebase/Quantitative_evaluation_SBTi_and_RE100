import pandas as pd
import numpy as np
import graphics
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from scipy import stats
from tabulate import tabulate


class G500:
    """
    Parent class for all ICIs. Gives standardized methods for data fetching, energy and emission calculations.
    """
    FIG_PATH = '/home/ivan/Documents/GitHub/G500_database/figures/'
    THESIS_PATH = '/home/ivan/Documents/GitHub/Thesis/src/python images/'
    PATH = "/home/ivan/Documents/GitHub/G500_database/data/"

    S2MB_INSTRUMENTS = ["unbundled eac", "energy product w/eac", "energy product no eac",
                        "hsc agreement", "ppa direct line",	"ppa w/eac", "ppa no eac"]

    def __init__(self, initialize=True):
        self.central = pd.read_csv(self.PATH + 'G500_central.csv', index_col=0, header=[0])
        self.energy = pd.read_csv(self.PATH + 'G500_energy.csv', index_col=0, header=[0])
        self.emissions = pd.read_csv(self.PATH + 'G500_emissions.csv', index_col=0, header=[0])
        self.s2mb = pd.read_csv(self.PATH + 'G500_S2MB.csv', index_col=0, header=[0])
        self.verification = pd.read_csv(self.PATH + "G500_verification.csv", header=[0, 1], index_col=0)

        self.years = list(range(2015, 2020))

        self.ini_flag = False

        self.s1_s2 = None

        self.total_electricity = None
        self.total_re_electricity = None
        self.re_electricity_ratios = None
        self.mini_energy_sectors = None

        if initialize:
            self.initialize()

    def initialize(self):
        if not self.ini_flag:
            self.fill_emissions()
            self.s1_s2 = self.get_emissions_s1_s2()

            self.total_electricity = self.get_energy_total_electricity_used()
            self.total_re_electricity = self.get_energy_total_re_electricity_used()
            self.re_electricity_ratios = self.get_energy_re_electricity_ratio()

            self.ini_flag = True

    def fill_emissions(self):
        """
        Wrapper method for emissions filling
        :return:
        """
        self.fill_s2_emissions()
        self.fill_combined_emissions()

    def fill_s2_emissions(self):
        """
        Fills the generic S2 column with S2 MB if available, otherwise S2 LB.
        This is only meant for quick calculations, and does not replace the targeted scope for initiative-specific
        comparisons/metrics.
        MB is preferred because it is the commonly reported, and is affected by RE purchasing instruments, while LB is
        not.
        :return:
        """
        for i in range(2015, 2020):
            year = ' ' + str(i)
            self.emissions['S2'+year] = np.nan
            for index in self.emissions.index:
                if pd.isna(self.emissions.loc[index, 'S2 MB'+year]):
                    self.emissions.loc[index, 'S2'+year] = self.emissions.loc[index, 'S2 LB'+year]
                else:
                    self.emissions.loc[index, 'S2' + year] = self.emissions.loc[index, 'S2 MB' + year]

    def fill_combined_emissions(self):
        """
        Fills S1+2 and S1+2+3 columns, making sure there are no empty spots.
        Useful for quick number-gathering.
        IMPORTANT: call self.fill_s2_emissions() before running this!!!!!
        :return:
        """
        for i in range(2015, 2020):
            year = ' ' + str(i)
            s1 = self.emissions['S1'+year]
            s2 = self.emissions['S2'+year]
            s3 = self.emissions['S3'+year].fillna(0)

            self.emissions['S1+2'+year] = s1 + s2
            self.emissions['S1+2+3'+year] = s1 + s2 + s3

    def print_company_emissions(self, name):
        """
        Quick printing of emission values for a company. For debugging.
        :param name: company to print
        :return:
        """
        # Ensure initialization has been run
        self.initialize()
        print(name)
        for i in range(2015, 2020):
            year = ' ' + str(i)
            print(str(i), 'S1', self.emissions.loc[name, 'S1' + year],
                  'S2 LB', self.emissions.loc[name, 'S2 LB' + year],
                  'S2 MB', self.emissions.loc[name, 'S2 MB' + year],
                  'S3', self.emissions.loc[name, 'S3' + year])
            print('S1+2', self.emissions.loc[name, 'S1+2' + year],
                  'S1+2+3', self.emissions.loc[name, 'S1+2+3' + year])

    def prune_index_with_central(self, column, value, exclude=True):
        """
        Prune all the dataframes by selecting a value in the central database. Works for ALL central columns!
        This is necessary because databases are kept separate (to aid in organisation).
        :param column: completed, country, headquarters, sector, etc.
        :param value: value used for pruning
        :param exclude: if True, remove companies that fit the criteria. If False, leave only those that fulfill it.
        :return:
        """
        if exclude:
            return self.central[self.central[column] != value].index.to_list()
        else:
            return self.central[self.central[column] == value].index.to_list()

    def prune_incomplete(self):
        """
        Quick elimination of incomplete companies.
        :return:
        """
        return self.prune_index_with_central('completed', 'yes', exclude=False)

    def remove_utilities_in_index(self, index):
        """
        Detect utility companies in an index, and remove them.
        :param index:
        :return:
        """
        utilities = []
        for i in index:
            if self.central.loc[i, 'energy sector'] == "Electricity Generation":
                utilities.append(i)
        return index.drop(utilities)

    def group_central_by_column_value(self, index, column_name):
        """
        Disaggregate companies using the values of a column in the central database.
        :param index: a group of companies
        :param column_name: name of the column you want to categorize
        :return:
        """
        central = self.central.loc[index]
        names = central.value_counts(column_name).index

        groups = {}
        for name in names:
            groups[name] = central[central[column_name] == name].index.to_list()
        return groups

    def get_df_sum_emissions(self):
        """
        Returns a dataframe indexed by year with the sum of emissions of all companies
        :return:
        """
        n_columns = int(len(self.emissions.columns)/5)
        column_names = self.emissions.columns.to_list()
        column_names = column_names[:n_columns]
        column_names = [name.replace(' 2015', '') for name in column_names]

        sum_emissions = self.emissions.sum()

        values = {k: [] for k in column_names}
        for i in range(2015, 2020):
            year = ' ' + str(i)
            for key in values:
                values[key].append(sum_emissions[key+year])

        values = pd.DataFrame.from_dict(values)
        values.index = [i for i in range(2015, 2020)]

        return values

    def get_df_sum_energy(self):
        """
        Returns a dataframe indexed by year with the sum of energy of all companies
        :return:
        """
        n_columns = int(len(self.energy.columns) / 5)
        column_names = self.energy.columns.to_list()
        column_names = column_names[:n_columns]
        column_names = [name.replace(' 2015', '') for name in column_names]

        sum_energy = self.energy.sum()

        values = {k: [] for k in column_names}
        for i in range(2015, 2020):
            year = ' ' + str(i)
            for key in values:
                values[key].append(sum_energy[key + year])

        values = pd.DataFrame.from_dict(values)
        values.index = [i for i in range(2015, 2020)]

        return values

    def get_company_emissions_s2(self, company):
        """
        Get the S2 values of a company (MB if available, LB otherwise)
        :param company: company name
        :return:
        """
        columns = ["S2 " + str(i) for i in self.years]
        s2 = self.emissions.loc[company, columns]

        return pd.Series(data=s2.values, index=self.years, name=company)

    def get_company_emissions_s1_s2(self, company):
        """
        Get the S1+2 emissions of a company (S2 MB used if available, LB otherwise)
        :param company: company name
        :return:
        """
        columns = ["S1+2 " + str(i) for i in self.years]
        s1_s2 = self.emissions.loc[company, columns]

        return pd.Series(data=s1_s2.values, index=self.years, name=company)

    def get_company_energy_total_electricity_used(self, company):
        """
        Get the sum of purchased electricity and self-generated self-consumed electricity
        :param company:
        :return:
        """
        electricity = []

        for i in range(2015, 2020):
            year = ' ' + str(i)
            total = self.energy.loc[company, 'ct purchased electricity' + str(year)]
            total += self.energy.loc[company, 'gt self-cons electricity' + str(year)]

            electricity.append(total)

        return pd.Series(data=electricity, index=list(range(2015, 2020)), name=company)

    def get_company_energy_total_re_electricity_used(self, company):
        """
        Get the sum of purchased renewable electricity and self-generated self-consumed renewable electricity
        :param company: company name
        :return:
        """
        re_electricity = []

        for i in range(2015, 2020):
            year = ' ' + str(i)
            renewable = self.energy.loc[company, 'cr purchased electricity' + str(year)]
            renewable += self.energy.loc[company, 'gr self-cons electricity' + str(year)]

            re_electricity.append(renewable)

        return pd.Series(data=re_electricity, index=list(range(2015, 2020)), name=company)

    def get_company_energy_re_electricity_ratio(self, company):
        """
        Calculate the ratio of renewables in the total consumed electricity for a company
        :param company: name
        :return:
        """
        ratios = []
        total = self.get_company_energy_total_electricity_used(company)
        renewable = self.get_company_energy_total_re_electricity_used(company)
        for i in range(2015, 2020):
            ratios.append(renewable[i]/total[i])

        return pd.Series(data=ratios, index=list(range(2015, 2020)), name=company)

    def get_emissions_s2(self):
        """
        Get a dataframe with the S2 emissions of all companies
        :return: [index=companies, columns=2015--2019], in tCO2e
        """
        s2 = pd.DataFrame(index=self.emissions.index, columns=self.years)
        for company in s2.index:
            s2.loc[company] = self.get_company_emissions_s2(company)
        return s2

    def get_emissions_s1_s2(self):
        """
        Get a dataframe with the S1+2 emissions of all companies
        :return: [index=companies, columns=2015--2019], in tCO2e
        """
        s1_s2 = pd.DataFrame(index=self.emissions.index, columns=self.years)
        for company in s1_s2.index:
            s1_s2.loc[company] = self.get_company_emissions_s1_s2(company)
        return s1_s2

    def get_from_emissions(self, name, index):
        """
        Get a dataframe of a specific column in the emissions .csv file
        :param name: column name in the .csv file, without the year
        :param index: list of companies to fetch
        :return:
        """
        columns = [name + " " + str(i) for i in self.years]
        df = self.emissions.loc[index, columns]
        df.columns = self.years
        return df

    def get_from_energy(self, name, index):
        """
        Get a dataframe of a specific column in the energy .csv file
        :param name: column name in the .csv file, without the year
        :param index: list of companies to fetch
        :return:
        """
        columns = [name + " " + str(i) for i in self.years]
        df = self.energy.loc[index, columns]
        df.columns = self.years
        return df

    def get_energy_total_electricity_used(self):
        """
        Get a dataframe with the total electricity consumed for all companies
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns = ["ct purchased electricity " + str(i) for i in self.years]
        purchased = self.energy.loc[self.energy.index, columns]
        purchased.columns = self.years

        columns = ["gt self-cons electricity " + str(i) for i in self.years]
        self_consumed = self.energy.loc[self.energy.index, columns]
        self_consumed.columns = self.years

        return purchased + self_consumed

    def get_energy_total_re_electricity_used(self):
        """
        Get a dataframe with the total renewable electricity consumed for all companies
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns = ["cr purchased electricity " + str(i) for i in self.years]
        purchased = self.energy.loc[self.energy.index, columns]
        purchased.columns = self.years

        columns = ["gr self-cons electricity " + str(i) for i in self.years]
        self_consumed = self.energy.loc[self.energy.index, columns]
        self_consumed.columns = self.years

        return purchased + self_consumed

    def get_electricity_self_consumed_re(self):
        """
        Get a dataframe with the total self-generated and consumed renewable electricity for all companies
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns = ["gr self-cons electricity " + str(i) for i in self.years]
        self_consumed_re = self.energy.loc[self.energy.index, columns]
        self_consumed_re.columns = self.years

        return self_consumed_re

    def get_energy_re_electricity_ratio(self):
        """
        Calculate the ratio of renewable electricity in total electricity for all companies
        :return: [index=companies, columns=2015--2019], in MWh
        """
        renewable_ratios = pd.DataFrame(index=self.energy.index, columns=self.years)
        for company in renewable_ratios.index:
            renewable_ratios.loc[company] = self.get_company_energy_re_electricity_ratio(company)

        return renewable_ratios

    def get_energy_re_purchases(self, index):
        """
        Get a dataframe with the total energy purchased for all companies
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns_elec = ['cr purchased electricity' + " " + str(i) for i in self.years]
        df_elec = self.energy.loc[index, columns_elec]
        df_elec.columns = self.years

        columns_hsc = ['cr purchased hsc' + " " + str(i) for i in self.years]
        df_hsc = self.energy.loc[index, columns_hsc]
        df_hsc.columns = self.years

        return df_elec + df_hsc

    def get_s2mb_re_purchases_reported(self, index):
        """
        Get a dataframe with the sum of "reported" renewable energy (may or may not have disclosed instruments)
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns = ["total" + " " + str(i) for i in self.years]
        reported = self.s2mb.loc[index, columns]
        reported.columns = self.years
        return reported

    def get_s2mb_re_purchases_instrument(self, instrument):
        """
        Get a dataframe with the renewable energy disclosed for a specific market instrument for all companies
        :param instrument: name of instrument in .csv file
        :return: [index=companies, columns=2015--2019], in MWh
        """
        columns = [instrument + " " + str(i) for i in self.years]
        energy = self.s2mb.loc[self.s2mb.index, columns]
        energy.columns = self.years
        return energy

    def get_s2mb_energy_all_instruments(self):
        """
        Get a dataframe with the sum of renewable energy purchased through all instruments (aka "transparent")
        :return: [index=companies, columns=2015--2019], in MWh
        """
        all_instruments = {}
        for instrument in self.S2MB_INSTRUMENTS:
            all_instruments[instrument] = self.get_s2mb_re_purchases_instrument(instrument)

        return all_instruments

    def get_mini_energy_sectors(self):
        """
        Legacy function. Unused.
        :return:
        """
        mini_energy_sectors = pd.read_csv(self.PATH + 'mini databases/energy sectors.csv', index_col=0, header=[0],
                                          squeeze=True)
        sectors = {}
        for company in self.central.index:
            sectors[company] = mini_energy_sectors[self.central.loc[company, 'industry']]

        sectors = pd.Series(sectors)
        self.mini_energy_sectors = sectors
        return sectors

    def get_sum_profits(self):
        """
        Add all the profits of G500 firms (2019 data)
        :return:
        """
        prof_txt = self.central['profits ($M)']
        values = [v.replace('$', '') for v in prof_txt]
        values = [float(v.replace(',', '')) for v in values]
        return sum(values)

    def get_sum_revenues(self):
        """
        Add all the revenues of G500 firms (2019 data)
        :return:
        """
        rev_txt = self.central['revenues ($M)']
        values = [v.replace('$', '') for v in rev_txt]
        values = [float(v.replace(',', '')) for v in values]
        return sum(values)

    def get_sum_market_value(self):
        """
        Add all the market cap of G500 firms (2019 data)
        :return:
        """
        mark_val_txt = self.central['market value ($M)']
        values = []
        missing = 0
        for m in mark_val_txt:
            if m != '$' and m != '$-':
                tmp = m.replace('$', '')
                values.append(float(tmp.replace(',', '')))
            else:
                values.append(0)
                missing += 1
        return [sum(values), missing]

    @staticmethod
    def sort_series_by_year(series):
        """
        Sort a series by year. Useful after using panda's value_counts().
        :param series:
        :return:
        """
        series = series.sort_index(ascending=True)
        series.index = [int(i) for i in series.index]
        return series

    @staticmethod
    def calculate_aagr(values):
        """
        Simple annual average growth rate
        :param values: values to be calculated, like TWh or MtCO2e
        :return:
        """
        rates = []
        for i in range(len(values)-1):
            if values[i] != 0:
                rates.append(values[i+1]/values[i] - 1)
            else:
                return np.nan
        return sum(rates)/len(rates)

    def accumulate_series_by_year(self, series):
        """
        Add the data cumulatively in a yearly order.
        :param pd.Series series:
        :return:
        """
        series = self.sort_series_by_year(series)

        count = 0
        for year in series.index:
            count += series[year]
            series[year] = count

        return series


class PlotterG500:
    MAGNITUDE = 10 ** 6  # TWh for electricity, MtCO2e for GHG
    S2MB_INSTRUMENTS = {"U-EACs": ["unbundled eac"],
                        "Utility GPs": ["energy product w/eac", "energy product no eac", "hsc agreement"],
                        "PPAs": ["ppa direct line", "ppa w/eac", "ppa no eac"],
                        "Self-gen Elec": ["self consumed"], "Unknown": ['unknown']}
    S2MB_TRACE = {"w/EACs": ["unbundled eac", "energy product w/eac", "ppa w/eac"],
                  "no EACs": ["energy product no eac", "ppa no eac"],
                  "direct": ["ppa direct line", "hsc agreement"]}

    def __init__(self, init_data=True):
        """
        Plotter objects are a useful way to separate data management from visualizations
        :param init_data:
        """
        self.data = None
        self.name = None
        self.colors = graphics.COLORMAP
        if init_data:
            self.data = G500()
            self.name = "G500"

    def get_central_grouping(self, index, central_column, n_set_df=None):
        names = []
        indexes = []
        if n_set_df is not None:
            n_sets = []
        else:
            n_sets = None

        groups = self.data.central.loc[index, central_column].value_counts().index
        for group in groups:
            tmp = self.data.central.loc[index][self.data.central.loc[index, central_column] == group]
            indexes.append(tmp.index)
            names.append(group)
            if n_set_df is not None:
                n_sets.append(n_set_df.loc[tmp.index].count())

        return indexes, names, n_sets

    def run_by_central_grouping(self, index, central_column, function, n_set_source=None):
        groups, names, n_sets = self.get_central_grouping(index, central_column, n_set_source)

        for i, group in enumerate(groups):
            print('-'*20, '{:^20s}'.format(names[i]), '-'*20, sep="\n")
            if n_set_source:
                result = function(group, n_sets[i])
            else:
                result = function(group)
            if result is not None:
                print(result)

    def plot_line_electricity_totals(self, save=False):
        sum_energy = self.data.get_df_sum_energy()

        plt.figure()

        total = (sum_energy['ct purchased electricity'] + sum_energy['gt self-cons electricity']) / 10**6
        total.name = 'Total electricity'
        total.plot.line(marker='o')

        purchased = sum_energy['ct purchased electricity']/10**6
        purchased.name = 'Purchased Total'
        purchased.plot.line(marker='o')

        renewable = (sum_energy['cr purchased electricity'] + sum_energy['gr self-cons electricity']) / 10**6
        renewable.name = 'Total RE'
        renewable.plot.line(marker='v')

        purch_re = sum_energy['cr purchased electricity'] / 10**6
        purch_re.name = 'Purchased RE'
        purch_re.plot.line(marker='v')

        plt.xlabel('year', fontweight='bold')
        plt.ylabel('TWh', fontweight='bold')
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))

        plt.xticks([i for i in range(2015, 2020)])

        plt.tight_layout()
        if save:
            graphics.save_figure("line_"+self.name+"_electricity_totals")

    def plot_energy(self, index, ax=None, legend=True):

        energy = pd.DataFrame(columns=self.data.years)
        energy.loc['RE Self-Gen'] = pd.DataFrame.sum(self.data.get_from_energy('cr self-gen non-fuel', index))
        energy.loc['RE Fuel'] = pd.DataFrame.sum(self.data.get_from_energy('cr fuel', index))
        energy.loc['NRE Fuel'] = pd.DataFrame.sum(self.data.get_from_energy('cnr fuel', index))
        energy.loc['RE Purchases'] = pd.DataFrame.sum(self.data.get_from_energy('cr purchased electricity', index))
        energy.loc['RE Purchases'] += pd.DataFrame.sum(self.data.get_from_energy('cr purchased hsc', index))
        energy.loc['NRE Purchases'] = pd.DataFrame.sum(self.data.get_from_energy('cnr purchased electricity', index))
        energy.loc['NRE Purchases'] += pd.DataFrame.sum(self.data.get_from_energy('cnr purchased hsc', index))
        energy = energy/self.MAGNITUDE

        colors = graphics.COLORBLIND
        colors = [colors[4], colors[1], colors[0]] + colors[2:4]

        if ax is None:
            _, ax = plt.subplots()
        total = pd.DataFrame.sum(self.data.get_from_energy("ct energy", index)) / self.MAGNITUDE
        ax.set_ylim(max(total) - max(total) * 1.025, max(total) * 1.025)

        energy.T.plot.area(ax=ax, color=colors, lw=0, legend=False)

        if legend:
            handles, labels = ax.get_legend_handles_labels()
            plt.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(1.2, 0.5), loc='center',
                       ncol=1, borderaxespad=0.1, fancybox=True)
        if ax is None:
            graphics.plot_config(y_label="TWh", int_xticks=True)
        return ax, energy

    def plot_line_purchased_re_elec_hsc(self, index, central_grouping=None, y_max=None, save=False, index_name=None,
                                        folder=None):
        years = self.data.years

        if central_grouping:
            groups, names, _ = self.get_central_grouping(index, central_grouping)
        else:
            groups = [index]
            names = []

        for i, group in enumerate(groups):
            purchases = pd.DataFrame(index=years)
            hsc = self.data.get_from_energy("cr purchased hsc", group) / self.MAGNITUDE
            purchases["HSC"] = pd.DataFrame.sum(hsc).astype('float64')
            electricity = self.data.get_from_energy("cr purchased electricity", group) / self.MAGNITUDE
            purchases["Electricity"] = pd.DataFrame.sum(electricity).astype('float64')

            fig, ax = plt.subplots()
            purchases.plot.area(ax=ax, rot=0, color=["#CC79A7", "#F0E442"], linewidth=0, legend=None)
            if y_max:
                ax.set_ylim(top=y_max)
            graphics.plot_config(y_label="Claimed\nRenewable Energy Purchases ($TWh$)", int_xticks=True)

            handles, labels = ax.get_legend_handles_labels()
            fig.legend(handles=reversed(handles), labels=reversed(labels), fancybox=True, ncol=1,
                       bbox_to_anchor=(1.005, 0.5), loc='right')
            fig.tight_layout(rect=[0, 0, 0.81, 1])

            if save:
                filename = "RE_energy_purchases_" + index_name + "_"
                if central_grouping:
                    graphics.save_figure(filename + names[i], folder=folder)
                else:
                    graphics.save_figure(filename + "all", folder=folder)

    def plot_line_s12_by_scope(self, index, ax=None, years=None, y_label=False):
        if ax is None:
            fig, ax = plt.subplots()
        if years is None:
            years = self.data.years

        s12 = pd.DataFrame(index=years)
        s1 = self.data.get_from_emissions('S1', index)
        s2 = self.data.get_from_emissions('S2', index)
        s12['Scope 1'] = pd.DataFrame.sum(s1) / self.MAGNITUDE
        s12['Scope 2'] = pd.DataFrame.sum(s2) / self.MAGNITUDE

        colors = graphics.get_colors(s12.columns)
        s12.plot.area(ax=ax, rot=0, color=colors, linewidth=0, alpha=0.8)
        if y_label:
            ax.set_ylabel("Scope 1+2 ($MtCO_{2}e$)", fontweight='bold')
        graphics.plot_config(ax=ax, int_xticks=True)

    def plot_line_s12_by_sector(self, index, sector_name='energy sector', y_label='Scopes 1+2 ($MtCO_{2}e$)',
                                legend=False, save_name=None):
        years = self.data.years
        s12 = self.data.get_emissions_s1_s2().loc[index] / self.MAGNITUDE
        sector_groups = (self.data.group_central_by_column_value(index, sector_name))

        cumulative = pd.Series(index=years).fillna(0)
        tmp = pd.Series(index=years).fillna(0)
        _, ax = plt.subplots()
        colors = graphics.get_colors(sector_groups.keys())
        markers = []
        for i, sector in enumerate(sector_groups):
            # Prepare data for the group
            companies = sector_groups[sector]
            tmp += s12.loc[companies].sum()

            plt.fill_between(years, cumulative, tmp, color=colors[i])
            cumulative = tmp.copy()

            label = sector + " (" + str(len(companies)) + ")"
            markers = [mlines.Line2D([], [], color=colors[i], label=label, linewidth=3)] + markers
        if legend:
            plt.legend(handles=markers, bbox_to_anchor=(0.5, 1.0), loc='lower center', ncol=2, fancybox=True)
        graphics.plot_config(y_label=y_label, int_xticks=True)

        if save_name:
            graphics.save_figure(save_name)

    def plot_pie_by_central(self, index, sector_name='energy sector', save_name=None, startangle=0):
        sector_groups = (self.data.group_central_by_column_value(index, sector_name))

        if (sector_name == "energy sector" or "gics sector") and len(sector_groups) < 9:
            colors = graphics.get_colors(sector_groups.keys())
        else:
            colors = graphics.get_color_scale('plasma', list(range(len(sector_groups))))

        sector_groups.keys()
        values = [len(sector_groups[k]) for k in sector_groups]
        labels = [k + " (" + str(len(sector_groups[k])) + ")" for k in sector_groups]

        graphics.pie(values, labels, color_list=colors, startangle=startangle)

        if save_name:
            graphics.save_figure(save_name)

    def plot_bar_robustness_verification(self, index, ax=None, years=None, percentage=None, by_statement=False):
        if ax is None:
            _, ax = plt.subplots()
        else:
            _ = ax.figure
        if years is None:
            years = self.data.years
        years = [str(y) for y in years]

        ver_types = ['None', 'Limited', 'Moderate', 'Reasonable', 'High']

        s1 = pd.DataFrame(index=years, columns=ver_types)
        s2 = pd.DataFrame(index=years, columns=ver_types)
        for year in years:
            s1.loc[year] = self.data.verification.loc[index, (year, 's1')].value_counts()
            s2.loc[year] = self.data.verification.loc[index, (year, 's2')].value_counts()

        scopes = [s1, s2]
        [s.fillna(0, inplace=True) for s in scopes]

        if by_statement:
            for i, s in enumerate(scopes):
                combined = pd.DataFrame(index=s1.index, columns=["None", "Negative", "Positive"])
                combined["None"] = s["None"]
                combined["Negative"] = s["Moderate"] + s["Limited"]
                combined["Positive"] = s["Reasonable"] + s["High"]
                scopes[i] = combined

        for i, s in enumerate(scopes):
            s.columns = [f"S{i+1} " + c for c in s.columns]

        if percentage:
            scopes = [s/len(index) for s in scopes]

        if by_statement:
            scopes[0].plot.bar(ax=ax, stacked=True, colormap='cividis', position=1.05, width=0.25, rot=0, legend=False)
            scopes[1].plot.bar(ax=ax, stacked=True, colormap='magma', position=-0.05, width=0.25, rot=0, legend=False)
        else:
            scopes[0].plot.bar(ax=ax, stacked=True, colormap='viridis', position=1.05, width=0.25, rot=0, legend=False)
            scopes[1].plot.bar(ax=ax, stacked=True, colormap='cividis', position=-0.05, width=0.25, rot=0, legend=False)

        if percentage:
            graphics.plot_config(ax=ax, y_ax_percent=True)
        ax.set_xlim(-.5, len(years) - 0.5)

    def plot_line_robustness_visibility(self, index, ax=None, years=None):
        if ax is None:
            _, ax = plt.subplots()
        if years is None:
            years = self.data.years

        # Prepare data
        visible = self.data.get_s2mb_re_purchases_reported(index)
        claimed = self.data.get_energy_re_purchases(index)
        bar = pd.DataFrame(index=years)
        line = pd.DataFrame(index=years)
        bar["Visible"] = pd.DataFrame.sum(visible) / self.MAGNITUDE
        bar["Claimed"] = pd.DataFrame.sum(claimed) / self.MAGNITUDE
        line["Visibility (%)"] = bar["Visible"] / bar["Claimed"]

        bar.plot.bar(ax=ax, legend=None, color=["#56B4E9", "#D55E00"])

        # Visibility line
        ax2 = line.plot(style='o--', c='b', ax=ax, use_index=False, secondary_y=True, mark_right=False, legend=None)
        ax2.grid(False)
        ax.grid(True)
        ax2.tick_params(axis='y', colors='blue', labelcolor='blue')
        graphics.plot_config(y_ax_percent=True, ax=ax2)
        ax2.set_ylim(0, 1.055)
        if years == self.data.years:
            ax2.axvline(1.5, color='black', linestyle='-')
            ax2.text(1.5, 0.05, 'CDP overhaul', rotation=90, ha='right')
            ax2.axvline(3.5, color='black', linestyle='-')
            ax2.text(3.5, 0.05, 'Financials overhaul', rotation=90, ha='right')

        return ax2

    def plot_implementation_market_instruments(self, index, ax=None):

        market_instruments = self.data.get_s2mb_energy_all_instruments()
        market_instruments["self consumed"] = self.data.get_electricity_self_consumed_re()
        visible = self.data.get_s2mb_re_purchases_reported(index)
        claimed = self.data.get_energy_re_purchases(index)
        market_instruments["unknown"] = claimed - visible

        group_market_inst = {key: market_instruments[key].loc[index] for key in market_instruments}
        results = pd.DataFrame(index=self.data.years, columns=self.S2MB_INSTRUMENTS.keys()).fillna(0)
        for s2mb_group in self.S2MB_INSTRUMENTS:
            for s2mb_instrument in self.S2MB_INSTRUMENTS[s2mb_group]:
                results[s2mb_group] += group_market_inst[s2mb_instrument].sum() / self.MAGNITUDE

        # Rearrange so Unknown shows first
        cols = results.columns.to_list()
        cols = cols[-1:] + cols[:-1]
        results = results[cols]

        colors = graphics.get_colors(results.columns.to_list())
        if ax is None:
            _, ax = plt.subplots()
        results.plot.area(ax=ax, rot=0, color=colors, linewidth=0, legend=None)
        graphics.plot_config(ax=ax, int_xticks=True)

        return ax

    def print_tab_lin_regress(self, df, n_companies):
        table = pd.DataFrame(index=df.index)
        for row in df.index:
            values = df.loc[row].values.tolist()
            aagr = self.data.calculate_aagr(values)
            slope, intercept, r_value, p_value, std_err = stats.linregress(self.data.years, values, alternative="less")
            table.loc[row, 'Companies'] = n_companies
            table.loc[row, '2015'] = values[0]
            table.loc[row, '2019'] = values[-1]
            table.loc[row, 'AAGR'] = str(round(aagr * 100, 3)) + '%'
            table.loc[row, 'slope'] = slope
            table.loc[row, 'r'] = r_value
            table.loc[row, 'r^2'] = r_value ** 2
            table.loc[row, 'p'] = p_value
            table.loc[row, 'std_err'] = std_err
        print(tabulate(table, headers='keys', tablefmt='psql', floatfmt=".3f"))

    def stats_energy(self, index):
        energy = pd.DataFrame(columns=self.data.years)
        energy.loc['RE Self-Gen'] = pd.DataFrame.sum(self.data.get_from_energy('cr self-gen non-fuel', index))
        energy.loc['RE Fuel'] = pd.DataFrame.sum(self.data.get_from_energy('cr fuel', index))
        energy.loc['NRE Fuel'] = pd.DataFrame.sum(self.data.get_from_energy('cnr fuel', index))
        energy.loc['RE Purchases'] = pd.DataFrame.sum(self.data.get_from_energy('cr purchased electricity', index))
        energy.loc['RE Purchases'] += pd.DataFrame.sum(self.data.get_from_energy('cr purchased hsc', index))
        energy.loc['NRE Purchases'] = pd.DataFrame.sum(self.data.get_from_energy('cnr purchased electricity',
                                                                                 index))
        energy.loc['NRE Purchases'] += pd.DataFrame.sum(self.data.get_from_energy('cnr purchased hsc', index))

        energy.loc['Total RE'] = energy.loc['RE Fuel']+energy.loc['RE Purchases']+energy.loc['RE Self-Gen']
        energy.loc['Total NRE'] = energy.loc['NRE Fuel'] + energy.loc['NRE Purchases']
        energy.loc['Total Fuel'] = energy.loc['RE Fuel'] + energy.loc['NRE Fuel']
        energy.loc['Total Purchases'] = energy.loc['RE Purchases'] + energy.loc['NRE Purchases']
        energy.loc['Total Energy'] = pd.DataFrame.sum(energy.loc['RE Self-Gen':'NRE Purchases'])

        energy = energy / self.MAGNITUDE

        self.print_tab_lin_regress(energy, len(index))

    def stats_market_instruments(self, index):

        market_instruments = self.data.get_s2mb_energy_all_instruments()
        market_instruments["self consumed"] = self.data.get_electricity_self_consumed_re()
        visible = self.data.get_s2mb_re_purchases_reported(index)
        claimed = self.data.get_energy_re_purchases(index)
        market_instruments["unknown"] = claimed - visible

        group_market_inst = {key: market_instruments[key].loc[index] for key in market_instruments}
        results = pd.DataFrame(columns=self.data.years, index=self.S2MB_INSTRUMENTS.keys())
        results = results.fillna(0)
        for s2mb_group in self.S2MB_INSTRUMENTS:
            for s2mb_instrument in self.S2MB_INSTRUMENTS[s2mb_group]:
                results.loc[s2mb_group] += group_market_inst[s2mb_instrument].sum() / self.MAGNITUDE

        results.loc['Total'] = pd.DataFrame.sum(results)

        self.print_tab_lin_regress(results, len(index))
        return results

    def stats_scope_12(self, index):

        results = pd.DataFrame(columns=self.data.years)
        results.loc['S1'] = pd.DataFrame.sum(self.data.get_from_emissions('S1', index))
        results.loc['S2'] = pd.DataFrame.sum(self.data.get_from_emissions('S2', index))
        results.loc['S1+2'] = pd.DataFrame.sum(results)
        results = results/self.MAGNITUDE

        self.print_tab_lin_regress(results, len(index))

    def table_scope_disaggregation(self, index):
        s1 = self.data.get_from_emissions("S1", index)
        s2 = self.data.get_from_emissions("S2", index)
        s2_mb = self.data.get_from_emissions("S2 MB", index)
        s2_lb = self.data.get_from_emissions("S2 LB", index)

        total = pd.DataFrame(index=["S1", "S2 LB", "S2 MB"], columns=self.data.years).fillna(0)
        for i in index:
            for y in self.data.years:
                total.loc["S1", y] += s1.loc[i, y]
                if s2.loc[i, y] == s2_mb.loc[i, y]:
                    total.loc["S2 MB", y] += s2_mb.loc[i, y]
                elif s2.loc[i, y] == s2_lb.loc[i, y]:
                    total.loc["S2 LB", y] += s2_lb.loc[i, y]
                else:
                    raise ValueError("Scope 2 did not match any value for company", i, y)

        total = total / 10**6
        print(tabulate(total, headers='keys', tablefmt='psql', floatfmt=".2f"))

    def stats_scope_12_descriptive(self, index):
        s1 = self.data.get_from_emissions('S1', index) / self.MAGNITUDE
        s2 = self.data.get_from_emissions('S2', index) / self.MAGNITUDE
        scopes = [s1, s2, s1+s2]

        columns = pd.MultiIndex.from_arrays([[2015]*5+[2019]*5, ['n', 'mean', 'median', 'min', 'max']*2])
        table = pd.DataFrame(index=['S1', 'S2', 'S1+2'], columns=columns)
        for i, scope in enumerate(table.index):
            for year in table.columns.get_level_values(0):
                tmp_scope = scopes[i]
                table.loc[scope, (year, 'n')] = len(index)
                table.loc[scope, (year, 'mean')] = tmp_scope[year].mean()
                table.loc[scope, (year, 'median')] = tmp_scope[year].median()
                table.loc[scope, (year, 'min')] = tmp_scope[year].min()
                table.loc[scope, (year, 'max')] = tmp_scope[year].max()

        print(tabulate(table, headers='keys', tablefmt='psql', floatfmt=".3f"))

    def thesis(self):
        pass
