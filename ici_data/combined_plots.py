import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from g500 import G500
from g500 import PlotterG500
from re100 import RE100
from sbti import SBTi
import graphics
import nat_earth

PATH = "/data/"
FIG_PATH = '/home/ivan/Documents/GitHub/G500_database/figures/'


def generator_remove_upper(limit):
    def inner_autopct(pct):
        return ('%.1f%%' % pct) if pct < limit else ''
    return inner_autopct


class CombinedPlots:

    def __init__(self):
        self.g500 = G500()
        self.re100 = RE100()
        self.sbti = SBTi()
        self.doubles_index = self.get_double_membership_index()
        self.only_sbti_index = self.sbti.central.drop(self.doubles_index, axis=0).index
        self.only_re100_index = self.re100.central.drop(self.doubles_index, axis=0).index
        self.colors = graphics.COLORMAP

    def get_double_membership_index(self):
        sbti_df = self.sbti.central
        re100_df = self.re100.central
        doubles_index = sbti_df.index.intersection(re100_df.index)
        return doubles_index

    def plot_pie_members(self, save=False):

        t_g500 = len(self.g500.central.index)
        t_double = len(self.doubles_index)
        t_sbti = len(self.sbti.central.index)-t_double
        t_re100 = len(self.re100.central.index)-t_double
        t_ici = t_sbti + t_re100 + t_double
        t_non_ici = t_g500 - t_ici

        labels = ['ICI members ('+str(t_ici)+')', 'Rest of G500 ('+str(t_non_ici)+')']
        values = [t_ici, t_non_ici]
        sub_labels = ['SBTi only ('+str(t_sbti)+')', 'SBTi and RE100 ('+str(t_double)+')',
                      'RE100 only ('+str(t_re100)+')']
        sub_values = [t_sbti, t_double, t_re100, t_non_ici]

        colors = self.colors

        plt.figure()

        _, _, autopcts = plt.pie(values, radius=1, colors=[colors['ICI'], colors['G500']],
                                 autopct=generator_remove_upper(70), startangle=315,
                                 pctdistance=0.85, wedgeprops=dict(width=0.3, edgecolor='white'),
                                 explode=(.2, 0))
        plt.setp(autopcts, **{'weight': 'bold', 'fontsize': 11})

        _, _, autopcts = plt.pie(sub_values, radius=0.6,
                                 colors=[colors['SBTi'], colors['Both'], colors['RE100'], colors['G500']],
                                 startangle=315, wedgeprops=dict(width=0.6, edgecolor='white'), autopct='%.1f%%',
                                 pctdistance=0.7, labeldistance=0.4)

        plt.setp(autopcts, **{'weight': 'bold', 'fontsize': 11})
        plt.legend(labels=labels+sub_labels)
        plt.tight_layout()

        plt.axis('equal')
        plt.show()

        if save:
            graphics.save_figure('G500 membership distribution')

    def plot_bar_countries(self, save=False):
        eu28 = graphics.EU_28
        tmp = self.g500.central[['country', 'any initiative']].copy()
        tmp['country'] = tmp['country'].replace(eu28, "EU27+UK")

        ici_countries = tmp[tmp.loc[:, "any initiative"] == 'yes'].value_counts("country")
        for index in tmp.index:
            country = tmp.loc[index, "country"]
            if country not in ici_countries.index:
                tmp.loc[index, 'country'] = "Other / No ICI"

        countries = pd.DataFrame(index=tmp.value_counts('country').index)
        countries['ICI'] = tmp[tmp.loc[:, "any initiative"] == 'yes'].value_counts("country")
        countries['G500'] = tmp.value_counts("country")
        countries = countries.sort_values(by='G500', ascending=True)

        labels = countries.columns.to_list()
        colors = graphics.get_colors(labels)
        labels = [i+" ("+str(int(countries[i].sum()))+')' for i in labels]
        groups = countries.index.to_list()
        values = [countries[i] for i in countries.columns]

        graphics.bar(values, groups, labels, colors, barh=True, num_show=True)
        graphics.plot_config(x_label="Companies", legend=True, legend_reverse=True)

        if save:
            graphics.save_figure("bar_G500_ICI_country")

    def plot_bar_wb_region(self, save=False):
        """
        Bar plot of World Bank distribution of G500 and ICI participation
        :param save:
        :return:
        """
        # Initialize dataframe with country names and UN Region
        geo = nat_earth.NaturalEarth()
        world = geo.get_db_country_to_wb_region()
        index = world.index
        index = [w.replace('United Kingdom', 'U.K.') for w in index]
        index = [w.replace('United States of America', 'U.S.') for w in index]
        world.index = index

        # Get dataframe with G500 and ICI numbers per country
        tmp = self.g500.central[['country', 'any initiative']].copy()
        g500_country = pd.DataFrame()
        g500_country['G500'] = tmp.value_counts("country")
        g500_country['ICI'] = tmp[tmp.loc[:, "any initiative"] == 'yes'].value_counts("country")

        g500_country = g500_country.fillna(0)

        # Initialize a dataframe for the regions
        regions = pd.DataFrame(index=world.value_counts("REGION_WB").index, columns=["ICI", 'G500'])
        regions = regions.fillna(0)
        for index in g500_country.index:
            if index in world.index:
                region = world[index]
            elif index == "Singapore":
                region = 'East Asia & Pacific'
            else:
                region = ''
                print(index, "was missing")

            regions.loc[region, 'G500'] = regions.loc[region, 'G500'] + g500_country.loc[index, 'G500']
            regions.loc[region, 'ICI'] = regions.loc[region, 'ICI'] + g500_country.loc[index, 'ICI']

        regions = regions.drop(index='Antarctica')
        regions = regions.sort_values('G500', axis=0)
        regions = regions.astype(int)

        labels = regions.columns.to_list()
        colors = graphics.get_colors(labels)
        labels = [i+" ("+str(int(regions[i].sum()))+')' for i in labels]

        values = [regions[c] for c in regions.columns]
        groups = regions.index.to_list()
        graphics.bar(values, groups, labels, colors, barh=True, num_show=True)
        graphics.plot_config(x_label="Companies", legend=True, legend_loc='lower right', legend_reverse=True)

        if save:
            graphics.save_figure("bar_G500_ICI_WB_region")

    def plot_stacked_ici_overlap_sector(self, sector, save=False):
        double_sectors = self.g500.central.loc[self.doubles_index, sector].value_counts()
        sbti_only_sectors = self.sbti.central.loc[self.only_sbti_index, sector].value_counts()
        re100_only_sectors = self.re100.central.loc[self.only_re100_index, sector].value_counts()

        double_sectors.name = 'Both'
        sbti_only_sectors.name = 'SBTi only'
        re100_only_sectors.name = 'RE100 only'

        df = pd.concat([double_sectors, sbti_only_sectors, re100_only_sectors], axis=1)
        df = df.fillna(0)
        df["Total"] = df[:].sum(axis=1)
        df = df.sort_values('Total')
        df = df.drop(columns='Total')

        df.columns = [c+" ("+str(df[c].sum().astype(int))+')' for c in df.columns]
        df.plot.barh(stacked=True, color=[self.colors['Both'], self.colors['SBTi'], self.colors['RE100']])
        graphics.plot_config(x_label='Companies')
        plt.xticks(np.arange(0, max(df.sum(axis=1)) + 1, 5))

        if save:
            graphics.save_figure('stacked_SBTi_RE100_'+sector)

    def plot_bar_g500_ici_sector_count(self, sector_name, save=False):
        """
        Prints a bar plot of sector membership distribution in all 3 groups
        :return:
        """
        central = self.g500.central.copy()
        # Get count of sectors in each group
        sec_g500 = central.value_counts(sector_name)
        sec_ici = central[central.loc[:, 'any initiative'] == 'yes'].value_counts(sector_name)
        grouping = pd.concat([sec_ici, sec_g500], axis=1)
        grouping.columns = ['ICI', 'G500']
        grouping = grouping.sort_values('G500')

        grouping = grouping.fillna(0)

        colors = graphics.get_colors(grouping.columns)
        labels = [c+' ('+str(int(sum(grouping[c])))+')' for c in grouping.columns]

        values = [grouping[c] for c in grouping.columns]
        groups = grouping.index.to_list()

        graphics.bar(values, groups, labels, colors, barh=True, num_show=True)
        graphics.plot_config(x_label="Companies", legend=True, legend_reverse=True)

        if save:
            graphics.save_figure("bar_"+sector_name+"_count")

    def plot_bar_energy_sector_percent(self, debug=False, save=False):

        # Get data
        self.g500.get_mini_energy_sectors()
        self.sbti.get_mini_energy_sectors()
        self.re100.get_mini_energy_sectors()

        t_g500 = len(self.g500.mini_energy_sectors.index)
        t_re100 = len(self.re100.mini_energy_sectors.index)
        t_sbti = len(self.sbti.mini_energy_sectors.index)

        g500_sector_cnt = self.g500.mini_energy_sectors.value_counts() / t_g500
        re100_sector_cnt = self.re100.mini_energy_sectors.value_counts() / t_re100
        sbti_sector_cnt = self.sbti.mini_energy_sectors.value_counts() / t_sbti

        # Fix names
        g500_sector_cnt.name = 'G500 (' + str(t_g500) + ')'
        sbti_sector_cnt.name = 'SBTi (' + str(t_sbti) + ')'
        re100_sector_cnt.name = 'RE100 (' + str(t_re100) + ')'
        # Plot
        plt.style.use('ggplot')
        temp = pd.concat([g500_sector_cnt, sbti_sector_cnt, re100_sector_cnt], axis=1)

        ax = temp.plot.barh(width=.8)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))  # turn y axis into percentage

        plt.title('Distribution of energy sectors\nin each group', fontweight='bold')
        plt.xlabel('% of total members', fontweight='bold')
        plt.legend()
        plt.tight_layout()

        if save:
            plt.savefig(FIG_PATH+'energy_sectors_percent.png')

        if debug:
            print('G500', g500_sector_cnt.sum(), t_g500, 'SBTi', sbti_sector_cnt.sum(), t_sbti,
                  'RE100', re100_sector_cnt.sum(), t_re100)

    def plot_emission_scopes(self, group, scopes=('S1', 'S2', 'S3'), title=None):
        if group == 'G500':
            sum_emissions = self.g500.get_df_sum_emissions()
        elif group == 'RE100':
            sum_emissions = self.re100.get_df_sum_emissions()
        elif group == 'SBTi':
            sum_emissions = self.sbti.get_df_sum_emissions()
        else:
            return

        maximum = 0

        plt.style.use('ggplot')
        fig = plt.figure()

        for scope in scopes:
            sum_scope = sum_emissions[scope] / 10 ** 6

            sum_scope.plot.line(marker='o')

            scope_max = sum_scope.max()
            if maximum < scope_max:
                maximum = scope_max

        if title:
            plt.title(title + ' GHG emissions in ' + group + ' companies', fontweight='bold')
        else:
            plt.title('-'.join(scopes) + ' GHG emissions for ' + group + ' companies', fontweight='bold')
        plt.xlabel('year', fontweight='bold')
        plt.ylabel('MtCO2e', fontweight='bold')
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))

        plt.xticks([i for i in range(2015, 2020)])
        plt.ylim(0, maximum * 1.1)

        plt.tight_layout()
        fig.show()

    def plot_emission_s3(self, group):
        scopes = ['S3'] + ['S3 C'+str(i) for i in range(1, 16)] + ['S3 other (upstream)', 'S3 other (downstream)']
        upstream = ['S3'] + ['S3 C' + str(i) for i in range(1, 9)] + ['S3 other (upstream)']
        downstream = ['S3'] + ['S3 C' + str(i) for i in range(9, 16)] + ['S3 other (downstream)']

        self.plot_emission_scopes(group, scopes=scopes, title='Scope 3')
        self.plot_emission_scopes(group, scopes=upstream, title='Upstream')
        self.plot_emission_scopes(group, scopes=downstream, title='Downstream')

    def thesis(self, save=False):
        self.plot_pie_members(save)
        self.plot_bar_countries(save)
        self.plot_bar_g500_ici_sector_count("gics sector", save)
        self.plot_bar_g500_ici_sector_count("energy sector", save)
        self.plot_stacked_ici_overlap_sector("gics sector", save)
        self.plot_stacked_ici_overlap_sector("energy sector", save)

    def plot_sbti_re100_sample_overlaps(self, save=False):
        years = self.re100.years

        re100_index = self.re100.index_analysis

        absolute = self.sbti.target_s12_tco2e.drop("Vodafone Group").index
        intensity = self.sbti.ici[self.sbti.ici['status'] == "Targets Set"].drop(self.sbti.target_s12_tco2e.index).index
        sbti_index = self.sbti.central.loc[absolute.append(intensity.drop('América Móvil'))].index

        overlap = re100_index[re100_index.isin(sbti_index)]
        re100_only = re100_index.drop(overlap)
        sbti_only = sbti_index.drop(overlap)

        results = pd.DataFrame(index=years)
        results["Scope 1 SBTi"] = self.sbti.get_from_emissions("S1", sbti_only).sum()
        results["Scope 2 SBTi"] = self.sbti.get_from_emissions("S2", sbti_only).sum()
        results["Scope 1 RE100"] = self.re100.get_from_emissions("S1", re100_only).sum()
        results["Scope 2 RE100"] = self.re100.get_from_emissions("S2", re100_only).sum()
        results["Scope 1 overlap"] = self.g500.get_from_emissions("S1", overlap).sum()
        results["Scope 2 overlap"] = self.g500.get_from_emissions("S2", overlap).sum()
        results = results / 10**6

        _, ax = plt.subplots()
        colors = ["#56B4E9", "#E69F00", "#0072B2", "#F0E442", "grey", "black"]
        results.plot.area(ax=ax, rot=0, linewidth=0, legend=None, color=colors, alpha=0.8)

        graphics.plot_config(title="GHG emission reductions and overlaps\nin 102 companies with targets",
                             y_label="Scope 1+2 ($MtCO_{2}e$)", int_xticks=True, legend=True, legend_reverse=True)
        if save:
            graphics.save_figure('combined_line_sbti_re100_overlap')
        plotter = PlotterG500()
        plotter.plot_implementation_market_instruments(sbti_only)
        if save:
            graphics.save_figure('sbti_only_market_instruments')
        plotter.plot_implementation_market_instruments(re100_only)
        if save:
            graphics.save_figure('re100_only_market_instruments')
        plotter.plot_implementation_market_instruments(overlap)
        if save:
            graphics.save_figure('overlap_market_instruments')

    def scope3(self):
        years = self.re100.years

        re100_index = self.re100.index_analysis
        absolute = self.sbti.target_s12_tco2e.drop("Vodafone Group").index
        intensity = self.sbti.ici[self.sbti.ici['status'] == "Targets Set"].drop(self.sbti.target_s12_tco2e.index).index
        sbti_index = self.sbti.central.loc[absolute.append(intensity.drop('América Móvil'))].index
        missing = re100_index[~re100_index.isin(sbti_index)]
        index = sbti_index.append(missing)

        s3 = self.g500.get_from_emissions('S3', index) / 10**6
        s2 = self.g500.get_from_emissions('S2', index) / 10 ** 6
        s1 = self.g500.get_from_emissions('S1', index) / 10 ** 6

        _, ax = plt.subplots()
        pd.DataFrame.sum(s3).plot(ax=ax, lw=2, color="#E69F00", label="All S3")

        df = pd.Series(index=years).fillna(0)
        for i in range(15):
            c = self.g500.get_from_emissions('S3 C%d' % (i+1), index) / 10**6
            for company in index:
                if c.loc[company].count() == 5:
                    df = df + c.loc[company]
        df.plot(ax=ax, lw=2, color="#D55E00", label="S3 reported in all years")
        pd.DataFrame.sum(s2).plot(ax=ax, lw=2, color="#F0E442", label="All S2")
        pd.DataFrame.sum(s1).plot(ax=ax, lw=2, color="#56B4E9", label="All S1")

        graphics.plot_config(y_label="Emissions ($MtCO_{2}e$)", int_xticks=True, legend=True)
        graphics.save_figure('scope3_line_sbti_re100')

    def plot_bar_emission_regions(self):
        years = self.re100.years

        re100_index = self.re100.index_analysis
        absolute = self.sbti.target_s12_tco2e.drop("Vodafone Group").index
        intensity = self.sbti.ici[self.sbti.ici['status'] == "Targets Set"].drop(self.sbti.target_s12_tco2e.index).index
        sbti_index = self.sbti.central.loc[absolute.append(intensity.drop('América Móvil'))].index
        missing = re100_index[~re100_index.isin(sbti_index)]
        index = sbti_index.append(missing)

        s12 = self.g500.get_from_emissions("S1+2", index) / 10**6
        results = pd.DataFrame(columns=years, index=self.g500.central['region'].value_counts().index)
        results = results.fillna(0)

        for company in s12.index:
            region = self.g500.central.loc[company, 'region']
            results.loc[region, years] += s12.loc[company]
            # results.loc[region, 'N'] += 1

        results = results.sort_values(2015, ascending=False)
        results.plot.bar(rot=90, color=graphics.COLORBLIND)
        graphics.plot_config(title="Emission reduction per world region\nof 102 companies with targets",
                             y_label="Scope 1+2 ($MtCO_{2}e$)")

    def get_all_stats(self):
        intensity = self.sbti.ici[self.sbti.ici['status'] == "Targets Set"].drop(self.sbti.target_s12_tco2e.index).index

        plotter = PlotterG500()

        plotter.plot_line_s12_by_scope(intensity)
        graphics.plot_config(title="Progress in 7 members with intensity targets")

        missing = ["CMA CGM", "Amazon", "Volvo", "X5 Retail Group", "Phoenix Group Holdings", "Fubon Financial Holding"]
        excluded = ['Starbucks', 'Adidas', 'Migros Group', 'Linde', 'Sumitomo Electric Industries', 'BMW',
                    'Facebook', 'Ford Motor', 'General Motors', 'Banco do Brasil', 'Credit Suisse Group']
        committed = self.sbti.ici[self.sbti.ici['status'] == "Committed"].index
        committed = committed.drop(excluded + missing)

        plotter.plot_line_s12_by_scope(committed)
        graphics.plot_config(title="Progress in 27 committed members")


test = CombinedPlots()
test.plot_sbti_re100_sample_overlaps()
