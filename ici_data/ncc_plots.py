import g500
import re100
import sbti
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import graphics
import unep
import ipcc_scenarios

matplotlib.use('Qt5Agg')
PATH = r"/home/ivan/Downloads/"


class NCCPlots:
    """
    Contains access to all datasets and plotters for G500, RE100 and SBTi.
    Also contains standardized indexes for relevant groupings in the paper (e.g., absolute SBTi targets only).
    Has functions to produce all figures in the paper.
    """
    def __init__(self):
        self.g500_plotter = g500.PlotterG500()
        self.re100_plotter = re100.PlotterRE100()
        self.sbti_plotter = sbti.PlotterSBTi()
        self.g500_data = self.g500_plotter.data
        self.re100_data = self.re100_plotter.data
        self.sbti_data = self.sbti_plotter.data

        # Build initiative indexes, including exclusive indexes
        absolute = self.sbti_data.target_s12_tco2e.index
        intensity = self.sbti_data.ici[self.sbti_data.ici['status'] == "Targets Set"].drop(absolute).index
        self.idx_sbti_abs = absolute.drop("Vodafone Group")
        self.idx_sbti_int = intensity.drop('América Móvil')
        self.idx_sbti = self.idx_sbti_abs.append(self.idx_sbti_int)
        self.idx_re100 = self.re100_data.index_analysis
        self.idx_overlap = self.idx_re100[self.idx_re100.isin(self.idx_sbti)]
        self.idx_re100_only = self.idx_re100.drop(self.idx_overlap)
        self.idx_sbti_only = self.idx_sbti.drop(self.idx_overlap)
        self.idx_all = self.idx_sbti_only.append(self.idx_re100_only.append(self.idx_overlap))
        # Special case for utilities
        central_all = self.g500_data.central.loc[self.idx_all]
        self.idx_utilities = central_all[central_all["energy sector"] == "Electricity Generation"].index
        self.idx_eii = central_all[central_all["energy sector"] == "Energy Intensive Industry"].index

    def plot_participants_sector_region(self):
        # Obtain ICI overlap
        idx_re100 = self.re100_data.central.index
        idx_sbti = self.sbti_data.central.index
        idx_overlap = idx_re100[idx_re100.isin(idx_sbti)]
        # Obtain individual groups
        idx_sbti = idx_sbti.drop(idx_overlap)
        idx_re100 = idx_re100.drop(idx_overlap)
        idx_g500 = self.g500_data.central[self.g500_data.central["any initiative"].isnull()].index
        # Construct data
        colors = ["G500", "Both", "SBTi", "RE100"]
        columns = ["Uncommitted G500", "SBTi and RE100", "Only SBTi", "Only RE100"]
        indexes = [idx_g500, idx_overlap, idx_sbti, idx_re100]
        fig, _ = plt.subplots(1, 2, figsize=(10, 4))
        axes = fig.get_axes()
        classifications = ['region', 'energy sector']

        for i, (name, ax) in enumerate(zip(classifications, axes)):
            df = pd.DataFrame(index=self.g500_data.central[name].unique(), columns=columns)
            for c, index in zip(columns, indexes):
                groups, names, _ = self.g500_plotter.get_central_grouping(index, name)
                for g, n in zip(groups, names):
                    df.loc[n, c] = len(g)
            df = df.reindex(pd.DataFrame.sum(df, axis=1).sort_values().index)
            df.plot.barh(ax=ax, stacked=True, color=graphics.get_colors(colors), legend=False)
            ax.set_xlim(0, 225)
            ax.set_xlabel("Companies", fontweight='bold')

        graphics.label_axes(fig, loc=[0, 1.05], fontweight='bold')
        fig.tight_layout(rect=[0, .06, 1, 1])
        fig.legend(loc='lower center', ncol=4, frameon=False,
                   labels=[columns[i] + " ($n=%d$)" % len(indexes[i]) for i in range(len(columns))])

    def table_sbti_data(self):
        targets = self.sbti_data.ici
        table = pd.DataFrame(data=0, index=["Committed", "1.5°C", "Well-below 2°C", "2°C"],
                             columns=["companies", "S1 abs", "S1 int", "S2 abs", "S2 int", "S3 abs", "S3 int"])
        for idx in targets.index:
            # Detect company status/qualification
            qualification = targets.loc[idx, "status"]
            if qualification == "Targets Set":
                qualification = targets.loc[idx, "qualification"]
            table.loc[qualification, 'companies'] += 1
            # Detect intensity targets
            if targets.loc[idx, "intensity target S1"] == "yes":
                table.loc[qualification, "S1 int"] += 1
            if targets.loc[idx, "intensity target S2"] == "yes":
                table.loc[qualification, "S2 int"] += 1
            if targets.loc[idx, "intensity target S3"] == "yes":
                table.loc[qualification, "S3 int"] += 1
            # Detect absolute targets
            s12_abs = False
            s3_abs = False
            for i in range(1, 8):
                scope = targets.loc[idx, "scope t%d" % i]
                if pd.isna(scope):
                    break
                elif "S1+2" in scope:
                    s12_abs = True
                elif "S3" in scope:
                    s3_abs = True
                else:
                    raise ValueError("Got unexpected target scope value", scope)

                if s12_abs is s3_abs is True:
                    break
            if s12_abs:
                table.loc[qualification, "S1 abs"] += 1
                table.loc[qualification, "S2 abs"] += 1
            if s3_abs:
                table.loc[qualification, "S3 abs"] += 1

        return table

    def plot_sbti_ambition(self, unep_gap_report=False, grouping=None, ipcc_region="World",
                           ipcc_models=("AIM/CGE 2.0", "GCAM 4.2", "WITCH-GLOBIOM 3.1")):
        """
        A nice big plot of target pathways of SBTi companies with absolute Scope 1+2 targets
        :param unep_gap_report: if True, UNEP data is used (only World)
        :param grouping: central column to use if one wishes to separate data (e.g., by sector, country...)
        :param ipcc_region: IPCC scenario region. World or R5OECD90+EU (expandable)
        :param ipcc_models: if not None, only the models specified here will be used. There are: AIM/CGE 2.0, GCAM 4.2,
        IMAGE 3.0.1, MESSAGE-GLOBIOM 1.0, REMIND-MAgPIE 1.5 and WITCH-GLOBIOM 3.1 .

        :return:
        """
        s12_index = self.idx_sbti_abs
        targets = self.sbti_data.target_s12_tco2e.loc[s12_index].drop('scope', axis=1)

        # Build groups
        evaluation_groups = []
        evaluation_names = []
        evaluation_n_sets = []
        if grouping:
            groups = self.sbti_data.central.loc[s12_index, grouping].value_counts().index
            for group in groups:
                tmp = self.sbti_data.central.loc[s12_index][self.sbti_data.central.loc[s12_index, grouping] == group]
                evaluation_groups.append(tmp.index)
                evaluation_n_sets.append(targets.loc[tmp.index].count())
                evaluation_names.append(group)
        else:
            evaluation_groups.append(s12_index)
            evaluation_n_sets.append(targets.loc[s12_index].count())
            evaluation_names.append("All")

        # Fill with baseline/final emission values
        for company in s12_index:
            base_yr = targets.loc[company].first_valid_index()
            targets.loc[company, :base_yr] = targets.loc[company, base_yr]

            target_yr = targets.loc[company].last_valid_index()
            targets.loc[company, target_yr:] = targets.loc[company, target_yr]

        # plotting: target trends, with no overlaps
        fig, axes = plt.subplots(2, 3)
        fig.set_figheight(7)
        fig.set_figwidth(10)
        for name, index, n_set, ax in zip(evaluation_names, evaluation_groups, evaluation_n_sets, fig.get_axes()):

            cumulative_targets = targets.loc[index].sum() / 10 ** 6
            cumulative_targets.loc[2015:2030].plot(ax=ax, linewidth=3, label="Targets",
                                                   color=graphics.get_colors(['Targets']))
            x_ticks = ax.get_xticks().tolist()
            graphics.show_sample_size_xticks(ax, x_ticks, n_set.loc[x_ticks], fix=True)

            # normalized benchmarks and baselines
            if unep_gap_report:
                norm_year = 2019
                norm = cumulative_targets.loc[norm_year]
                benchmarks = [unep.normalize(unep.get_current_policies_ghg(), norm_year, norm=norm),
                              unep.normalize(unep.get_1_5_ghg(), norm_year, norm=norm),
                              unep.normalize(unep.get_2_ghg(), norm_year, norm=norm)]
                labels = ["CNP", "1.5°C", "2°C"]
            else:
                norm_year = 2020
                norm = cumulative_targets.loc[norm_year]
                benchmarks = [unep.normalize(ipcc_scenarios.get_emissions_scenario("SSP2-Baseline", ipcc_region,
                                                                                   ipcc_models), norm_year, norm=norm),
                              unep.normalize(ipcc_scenarios.get_emissions_scenario("SSP1-26", ipcc_region, ipcc_models),
                                             norm_year, norm=norm),
                              unep.normalize(ipcc_scenarios.get_emissions_scenario("SSP1-19", ipcc_region, ipcc_models),
                                             norm_year, norm=norm)]
                labels = ["SSP2-Baseline", "SSP1-26", "SSP1-19"]
            colors = ["CNP", "1.5°C", "2°C"]
            styles = ["--", '-.', ':']
            for i, bench in enumerate(benchmarks):
                color = graphics.get_colors(colors[i])
                bench.mean().plot(linewidth=2.5, ax=ax, label=labels[i], color=color, style=styles[i])
                ax.fill_between(bench.columns, bench.iloc[0], bench.iloc[1], color=color, alpha=0.3)

            # Add extra text
            ax.set_title(name + "\n$n=%d$" % len(index))
            ax.axvline(norm_year, color='black', linestyle='--', lw=1)
            # ax.text(norm_year, cumulative_targets.loc[norm_year] * .6, '$n$=%d' % int(n_set.loc[norm_year]),
            #         rotation=90, ha='right')
            ax.yaxis.set_major_locator(plt.MaxNLocator(5))

        axes[-1, -1].axis("off")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        axes[-1, -1].legend(handles, labels, loc='upper left', frameon=False)

        ax = fig.add_subplot(111, frameon=False)
        ax.grid(False)
        plt.tick_params(labelcolor='none', which='both', top=False, bottom=False, left=False, right=False)
        plt.ylabel("Scope 1+2 ($MtCO_2e$)", fontweight='bold')
        plt.tight_layout()

    def plot_sbti_ambition2(self, ipcc_models=("AIM/CGE 2.0", "GCAM 4.2", "WITCH-GLOBIOM 3.1"),
                            ipcc_region="R5OECD90+EU"):
        """
        A nice big plot of target pathways of SBTi companies with absolute Scope 1+2 targets.
        :param ipcc_models: if not None, only the models specified here will be used. They are: AIM/CGE 2.0, GCAM 4.2,
        :param ipcc_region: World or R5OECD90+EU
        IMAGE 3.0.1, MESSAGE-GLOBIOM 1.0, REMIND-MAgPIE 1.5 and WITCH-GLOBIOM 3.1 .

        :return:
        """
        s12_index = self.idx_sbti_abs
        targets = self.sbti_data.target_s12_tco2e.loc[s12_index].drop('scope', axis=1)

        # Build groups
        evaluation_groups = []
        evaluation_names = []
        evaluation_n_sets = []

        grouping = "energy sector"
        groups = self.sbti_data.central.loc[s12_index, grouping].value_counts().index
        for group in groups:
            tmp = self.sbti_data.central.loc[s12_index][
                self.sbti_data.central.loc[s12_index, grouping] == group]
            evaluation_groups.append(tmp.index)
            evaluation_n_sets.append(targets.loc[tmp.index].count())
            evaluation_names.append(group)

        # Fill with baseline/final emission values
        for company in s12_index:
            base_yr = targets.loc[company].first_valid_index()
            targets.loc[company, :base_yr] = targets.loc[company, base_yr]

            target_yr = targets.loc[company].last_valid_index()
            targets.loc[company, target_yr:] = targets.loc[company, target_yr]

        # plotting: target trends, with no overlaps
        fig, axes = plt.subplots(2, 3)
        fig.set_figheight(7)
        fig.set_figwidth(10)
        for name, index, n_set, ax in zip(evaluation_names, evaluation_groups, evaluation_n_sets, fig.get_axes()):

            cumulative_targets = targets.loc[index].sum() / 10 ** 6
            cumulative_targets.loc[2015:2030].plot(ax=ax, linewidth=3, label="SBTi absolute targets",
                                                   color=graphics.get_colors(['Targets']))
            x_ticks = ax.get_xticks().tolist()
            graphics.show_sample_size_xticks(ax, x_ticks, n_set.loc[x_ticks], fix=True)

            norm_year = 2020
            norm = cumulative_targets.loc[norm_year]
            benchmarks = [unep.normalize(
                              ipcc_scenarios.get_emissions_scenario("SSP1-26", ipcc_region, ipcc_models),
                              norm_year, norm=norm),
                          unep.normalize(
                              ipcc_scenarios.get_emissions_scenario("SSP1-19", ipcc_region, ipcc_models),
                              norm_year, norm=norm)]
            labels = ["SSP1-26", "SSP1-19"]
            colors = ["2°C", "1.5°C"]
            for i, bench in enumerate(benchmarks):
                color = graphics.get_colors(colors[i])
                ax.fill_between(bench.columns, bench.iloc[0], bench.iloc[1], label=labels[i], color=color, alpha=0.4)

            # Add extra text
            ax.set_title(name + "\n$n=%d$" % len(index))
            ax.axvline(norm_year, color='black', linestyle='--', lw=1)
            ax.yaxis.set_major_locator(plt.MaxNLocator(5))

        axes[-1, -1].axis("off")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        for i in range(1, len(labels)):
            labels[i] = labels[i] + f" {ipcc_region}"
        axes[-1, -1].legend(handles, labels, loc='upper left', frameon=False)

        ax = fig.add_subplot(111, frameon=False)
        ax.grid(False)
        plt.tick_params(labelcolor='none', which='both', top=False, bottom=False, left=False, right=False)
        plt.ylabel("Scope 1+2 ($MtCO_2e$)", fontweight='bold')
        plt.tight_layout()

    def plot_re100_ambition(self, ipcc_region='World', models=("AIM/CGE 2.0", "GCAM 4.2", "WITCH-GLOBIOM 3.1"),
                            year_start=2015, year_end=2030):
        index = self.idx_re100
        target_ratios = self.re100_data.target_ratios.loc[index]
        n_set = target_ratios.count()
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

        # Boxplot
        ax = axes[0]
        ratios = target_ratios.loc[index, year_start:year_end].astype(float)
        ratios.plot.box(ax=ax, showfliers=True, flierprops={'marker': '.', 'markersize': 8, "markeredgecolor": 'grey'})
        colors = ["SSP1-1.5 OECD"]
        for ssp, color in zip(["SSP1-19"], colors):
            scenario = ipcc_scenarios.get_electricity_scenario_ratio(ssp, ipcc_region, year_start=year_start,
                                                                     year_end=year_end, models=models)
            x_tick_pos = list(range(1, len(scenario.columns) + 1))  # Fix line+box odd behavior
            color = graphics.get_colors(color)[0]

            mini = scenario.loc['min']
            maxi = scenario.loc['max']
            ax.fill_between(x_tick_pos, mini, maxi, color=color, alpha=.5, label=ssp+f" {ipcc_region}")

        ax.locator_params(axis='x', nbins=7)
        x_ticks = ax.get_xticks().astype(int).tolist()
        ax.xaxis.set_major_locator(graphics.mticker.FixedLocator(x_ticks))
        fix_ticks = [i + year_start-1 for i in x_ticks]
        ax.set_xticklabels(["%d\n$t$=%d" % (year_start-1 + x, n) for x, n in zip(x_ticks, n_set.loc[fix_ticks])])

        graphics.plot_config(ax=ax, y_label="Targeted RE in Total Electricity", y_ax_percent=True, legend=True,
                             legend_loc='lower right')
        # graphics.legend_add_marker(ax, "Outlier", '.', 'grey', markersize=8)

        median = plt.Line2D([], [], color='tab:purple', marker='_', markersize=5, label='Median', lw=1)
        whisker = plt.Line2D([], [], color='r', marker='$\u2336$', markersize=8, label='Whisker', linestyle="none",
                             lw=2)
        box = plt.Line2D([], [], color='r', marker="s", markersize=8, linestyle="none", label='IQR',
                         fillstyle='none', lw=2)
        outlier = plt.Line2D([], [], color='grey', marker=".", markersize=8, linestyle="none", label='Outlier',
                             fillstyle='none', lw=2)
        ssp1 = plt.Line2D([], [], color=graphics.get_colors("SSP1-1.5 OECD")[0], marker="s", markersize=8,
                          linestyle="none", label="SSP1-19", lw=2)
        legend_labels = [median, box, whisker, outlier, ssp1]
        ax.legend(handles=legend_labels, loc='lower right')

        ax.yaxis.set_major_locator(plt.MaxNLocator(5))

        # Line plot
        ax = axes[1]
        re_twh = self.re100_data.get_baseline_targeted_re_electricity_extended()
        re_twh = pd.DataFrame.sum(re_twh.loc[index])
        total_twh = self.re100_data.get_baseline_total_electricity_extended()
        total_twh = pd.DataFrame.sum(total_twh.loc[index])
        nre_twh = total_twh-re_twh
        ambition = pd.DataFrame([re_twh, nre_twh]).astype('float') / self.re100_plotter.MAGNITUDE
        ambition.index = ["Renewable", "Non-renewable"]
        ambition.loc[:, year_start:year_end].T.plot.bar(ax=ax, stacked=True,
                                                        color=graphics.get_colors(["Renewable", "Total"]),
                                                        linewidth=0, alpha=1, rot=90)

        # ambition.loc["Total", year_start:year_end].plot.line(ax=ax, color=graphics.get_colors(["Total"]),
        #                                                      linewidth=2, label="Total")
        # ambition.loc["Renewable", year_start:year_end].plot.area(ax=ax, color=graphics.get_colors(['Renewable']),
        #                                                          linewidth=2, label="Renewable", alpha=0.5)
        # ax.set_xticks(range(year_start, year_end+1, 3))
        ax.locator_params(axis='x', nbins=7)
        x_ticks = ax.get_xticks().astype(int).tolist()
        ax.xaxis.set_major_locator(graphics.mticker.FixedLocator(x_ticks))
        fix_ticks = [i + year_start for i in x_ticks]
        ax.set_xticklabels(["%d\n$t$=%d" % (year_start + x, n) for x, n in zip(x_ticks, n_set.loc[fix_ticks])],
                           rotation=0)
        ax.yaxis.set_major_locator(plt.MaxNLocator(8))
        graphics.label_axes(fig, loc=[0, 1.025], fontweight='bold')
        graphics.plot_config(ax=ax, y_label="Electricity ($TWh$)", legend=True, legend_loc='lower right',
                             legend_reverse=True)

    def plot_robustness(self, by_statement=False):
        """
        A combined plot of ratio of third-party verification usage (top row), and visibility into renewable instrument
        preferences (bottom row).

        Utilities are excluded from renewable instrument preferences, for obvious reasons.
        :return:
        """
        indexes = [self.idx_sbti_only, self.idx_overlap, self.idx_re100_only,
                   self.idx_sbti_only.drop(self.idx_utilities), self.idx_overlap, self.idx_re100_only]

        fig, axes = plt.subplots(2, 3)
        years = [2015, 2019]
        ver_max_height = 0
        vis_max_height = 0
        for i, (ax, index) in enumerate(zip(fig.get_axes(), indexes)):
            if i < 3:
                self.g500_plotter.plot_bar_robustness_verification(index, years=years, ax=ax, percentage=True,
                                                                   by_statement=by_statement)
                height = ax.get_ylim()[1]
                if ver_max_height < height:
                    ver_max_height = height
            else:
                self.g500_plotter.plot_line_robustness_visibility(index, years=years, ax=ax)
                height = ax.get_ylim()[1]
                if vis_max_height < height:
                    vis_max_height = height

        # Make plot pretty
        titles = ["Only SBTi", "SBTi and RE100", "Only RE100"]
        indexes += [0, 0, 0]
        for i, (ax, title, index) in enumerate(zip(fig.get_axes(), titles*3, indexes)):
            ax.yaxis.set_major_locator(plt.MaxNLocator(5))
            if i == 0:
                ax.set_ylabel("Companies (%)", fontweight='bold')
                graphics.label_axis(ax, 'a', loc=[0, 1.05], fontweight='bold')
            elif i == 3:
                ax.set_ylabel("RE Purchases\n($TWh$)", fontweight='bold')
                graphics.label_axis(ax, 'b', loc=[0, 1.05], fontweight='bold')
            elif i == 8:
                ax.set_ylabel("Visibility", fontweight='bold', color="blue", rotation=270, labelpad=10)
            else:
                ax.yaxis.set_ticklabels([])

            if i < 3:
                ax.set_title(title + "\n$n=%d$" % len(index))
                ax.set_ylim(0, ver_max_height)
                # ax.xaxis.set_ticklabels([])
            elif i < 6:
                ax.set_title(title + "\n$n=%d$" % len(index))
                ax.set_ylim(0, vis_max_height)
            else:
                pass
        fig.set_figwidth(10)
        fig.set_figheight(5)
        fig.tight_layout(rect=[0, 0, .84, 1])

        handles, labels = axes[0][0].get_legend_handles_labels()
        if by_statement:
            n_categories = 3
        else:
            n_categories = 5
        handles = handles[n_categories:] + handles[:n_categories]
        labels = labels[n_categories:] + ['S1']*n_categories
        tmp_legend = plt.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(1.025, 1.95),
                                loc='center left', ncol=2, columnspacing=0.5)
        fig.add_artist(tmp_legend)
        handles, labels = axes[1][0].get_legend_handles_labels()
        plt.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(1.3, 0.85), loc='center left')

    def plot_implementation(self):
        """
        Combined plot for LogFrame implementation indicators.
        Top row shows a disaggregated evolution of energy use in non-utilities, in three groupings
        Bottom row shows a disaggregated evolution of renewable energy purchase preferences.
        :return:
        """
        indexes = [self.idx_sbti_only.drop(self.idx_utilities), self.idx_overlap, self.idx_re100_only]
        titles = ["Only SBTi", "SBTi and RE100", "Only RE100"]
        fig, axes = plt.subplots(2, 3, figsize=(10, 5.5))
        en_max_height = 0
        rep_max_height = 0
        for i, (ax, index, title) in enumerate(zip(fig.get_axes(), indexes*2, titles*2)):
            if i < 3:
                self.g500_plotter.plot_energy(index, ax=ax, legend=False)
                height = ax.get_ylim()[1]
                if en_max_height < height:
                    en_max_height = height
            else:
                self.g500_plotter.plot_implementation_market_instruments(index, ax=ax)
                height = ax.get_ylim()[1]
                if rep_max_height < height:
                    rep_max_height = height

        # Make it pretty
        for i, (ax, index, title) in enumerate(zip(fig.get_axes(), indexes * 2, titles * 2)):
            ax.yaxis.set_major_locator(plt.MaxNLocator(5))
            if i == 0:
                ax.set_ylabel("Energy Used ($TWh$)", fontweight='bold')
                graphics.label_axis(ax, 'a', loc=[0, 1.05], fontweight='bold')
            elif i == 3:
                ax.set_ylabel("RE Sourcing\nModels ($TWh$)", fontweight='bold')
                graphics.label_axis(ax, 'b', loc=[0, 1.05], fontweight='bold')
            else:
                ax.yaxis.set_ticklabels([])
                ax.yaxis.set_major_locator(plt.MaxNLocator(5))

            if i < 3:
                ax.set_ylim(top=en_max_height)
                # ax.xaxis.set_ticklabels([])
                ax.xaxis.set_major_locator(plt.MaxNLocator(5))
                ax.set_title(title + "\n$n=%d$" % len(index))
            else:
                ax.set_ylim(top=rep_max_height)
                ax.set_title(title + "\n$n=%d$" % len(index))

        fig.tight_layout(rect=[0, 0, .84, 1])

        handles, labels = axes[0][0].get_legend_handles_labels()
        tmp_legend = plt.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(1.01, 2.15),
                                loc='center left', frameon=False)
        fig.add_artist(tmp_legend)
        handles, labels = axes[1][0].get_legend_handles_labels()
        plt.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(1.01, 0.7), loc='center left',
                   frameon=False)
        plt.tight_layout()

    def plot_substantive(self):
        """
        Create a plot of substantive indicators, comparing actual trends against targets when possible.
        Subdivided into SBTi absolute, SBTi intensity and RE100.
        :return:
        """
        fig, _ = plt.subplots(2, 2, figsize=(10, 9))
        axes = fig.get_axes()

        # SBTi absolute
        ax = axes[0]
        sbti_a_index = self.idx_sbti_abs
        years = self.g500_data.years
        sbti_targets = self.sbti_data.target_s12_tco2e.loc[sbti_a_index, years]
        sbti_a_nset = sbti_targets.count()
        magnitude = self.g500_plotter.MAGNITUDE

        s1, s2, sbti_targets = self.sbti_data.get_sbti_targeted_s12_results(sbti_a_index, extend_targets=True)

        s1 = (s1 / magnitude).astype('float64')
        s2 = (s2 / magnitude).astype('float64')
        results = s1 + s2
        sbti_targets = sbti_targets / magnitude

        sbti_targets.loc[sbti_a_index].sum().plot(ax=ax, style='o-', label="Targets", lw=2.5,
                                                  color=graphics.get_colors("Targets"))
        results.sum().plot(ax=ax, style='s-', label="Achieved", lw=2.5, color=graphics.get_colors('Achieved'))
        ax.fill_between(years, s1.sum(), s1.sum() + s2.sum(), color=graphics.get_colors('Scope 2'), alpha=0.8,
                        label="Scope 2")
        ax.fill_between(years, s1.sum(), color=graphics.get_colors('Scope 1'), alpha=0.8, label="Scope 1")
        graphics.show_sample_size_xticks(ax, years, sbti_a_nset, fix=True)
        graphics.plot_config(ax=ax, y_label="Scope 1+2 ($MtCO_2e$)")
        ax.set_title("SBTi Absolute\n$n=%d$" % len(sbti_a_index))
        ax.legend(fontsize='small', loc='lower left')
        ax.yaxis.set_major_locator(plt.MaxNLocator(6))

        # SBTi intensity
        ax = axes[1]
        sbti_i_index = self.idx_sbti_int
        self.g500_plotter.plot_line_s12_by_scope(sbti_i_index, ax=ax)
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles=reversed(handles), labels=reversed(labels), fontsize='small', loc='lower left')
        ax.set_title("SBTi Intensity\n$n=%d$" % len(sbti_i_index))
        sbti_i_nset = pd.Series(index=years, data=[3, 4, 6, 7, 7])
        graphics.show_sample_size_xticks(ax, years, sbti_i_nset, fix=True)
        graphics.plot_config(ax=ax, y_label="Scope 1+2 ($MtCO_2e$)")
        ax.yaxis.set_major_locator(plt.MaxNLocator(5))

        # RE100
        ax = axes[2]
        re100_index = self.idx_re100
        target_ratios = self.re100_data.target_ratios.loc[re100_index, years]
        re100_n_set = target_ratios.count()

        total, renewable, target_ratios = self.re100_data.get_re100_targeted_results(re100_index, extend_targets=False)
        targeted = pd.DataFrame.sum(total * target_ratios).astype(float) / magnitude
        renewable = pd.DataFrame.sum(renewable).astype(float) / magnitude
        total = pd.DataFrame.sum(total).astype(float) / magnitude

        targeted.plot(ax=ax, label="Targets", color=graphics.get_colors("Targets"), lw=2.5, style='o-', legend=None)
        total.plot(ax=ax, label="Total", color=graphics.get_colors("Total"), linewidth=2.5)
        renewable.plot.area(ax=ax, rot=0, color=graphics.get_colors('Renewable'), linewidth=0, alpha=0.8,
                            label="Achieved RE")
        graphics.show_sample_size_xticks(ax, years, re100_n_set, fix=True)
        graphics.plot_config(y_label="Electricity ($TWh$)", int_xticks=True, ax=ax)
        ax.set_title("RE100\n$n=%d$" % max(re100_n_set))
        ax.legend(loc='lower right', fontsize='small')
        ax.yaxis.set_major_locator(plt.MaxNLocator(6))

        # All
        ax = axes[3]
        self.plot_substantive_overlap(ax)
        ax.yaxis.set_major_locator(plt.MaxNLocator(6))
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles=reversed(handles), labels=reversed(labels), fontsize='small', loc='lower left')
        ax.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax.set_title("Substantive progress\n$n=102$")
        graphics.plot_config(ax=ax, y_label="Scope 1+2 ($MtCO_2e$)")

        graphics.label_axes(fig, loc=[0, 1.05], fontweight='bold')
        fig.tight_layout()

    def plot_normalized_e_factors(self, index=None, average=False):
        """
        Create a plot of S1, S2 MB and S2 MB emission factors that is normalized to make companies comparable.
        :param index: list of companies to include. Default: all 103 will be included
        :param average: if True, normalize with average EF. False (Default), use the earliest year with data instead.
        :return:
        """

        if index is None:
            index = self.g500_data.remove_utilities_in_index(self.idx_all)

        # Create emission factors for S1, S2 MB and S2 LB according to the methodology
        s1 = self.g500_data.get_from_emissions('S1', index)
        nr_fuel = self.g500_data.get_from_energy('cnr fuel', index)
        ef_s1 = s1/nr_fuel
        s2mb = self.g500_data.get_from_emissions('S2 MB', index)
        nr_purch = self.g500_data.get_from_energy('cnr purchased electricity', index)
        nr_purch += self.g500_data.get_from_energy('cnr purchased hsc', index)
        ef_s2mb = s2mb/nr_purch
        s2lb = self.g500_data.get_from_emissions('S2 LB', index)
        t_purch = self.g500_data.get_from_energy('ct purchased electricity', index)
        t_purch += self.g500_data.get_from_energy('ct purchased hsc', index)
        ef_s2lb = s2lb/t_purch
        normalized_efs = {"Scope 1": ef_s1, "Scope 2 market-based": ef_s2mb, "Scope 2 location-based": ef_s2lb}

        # Normalize for all scopes and companies
        for name in normalized_efs:
            for company in index:
                if average:
                    denominator = normalized_efs[name].loc[company].mean()
                else:
                    year = normalized_efs[name].loc[company].first_valid_index()
                    if not pd.isna(year):
                        denominator = normalized_efs[name].loc[company, year]
                    else:
                        denominator = np.nan
                normalized_efs[name].loc[company] = (normalized_efs[name].loc[company] / denominator) - 1

        fig, _ = plt.subplots(1, 3, figsize=(10, 3.5))
        axes = fig.get_axes()

        for i, name in enumerate(normalized_efs):
            normalized_efs[name].T.plot(ax=axes[i], title=name, legend=False)
            axes[i].axhline(y=0.9, ls='--', linewidth=1)
            graphics.plot_config(ax=axes[i], y_ax_percent=True)
            if average:
                axes[i].set_ylim(-1, 1)
            else:
                axes[i].set_ylim(-1, 2.5)
            if i > 0:
                axes[i].yaxis.set_ticklabels([])
            else:
                axes[i].set_ylabel("Emission Factor Deviation", weight='bold')
        plt.tight_layout()

        return normalized_efs

    def table_causal(self):
        re100_index = self.re100_data.index_analysis
        absolute = self.sbti_data.target_s12_tco2e.drop("Vodafone Group").index
        intensity = self.sbti_data.ici[self.sbti_data.ici['status'] == "Targets Set"]
        intensity = intensity.drop(self.sbti_data.target_s12_tco2e.index).index
        sbti_index = self.sbti_data.central.loc[absolute.append(intensity.drop('América Móvil'))].index
        missing = re100_index[~re100_index.isin(sbti_index)]
        index = sbti_index.append(missing)

        self.g500_plotter.run_by_central_grouping(index, "energy sector",
                                                  self.g500_plotter.stats_scope_12)

    def plot_substantive_overlap(self, ax):
        intensive = self.idx_utilities
        intensive = intensive.append(self.idx_eii)
        overlap = self.idx_overlap
        re100_only = self.idx_re100_only
        sbti_no_intensive = self.idx_sbti_only.drop(intensive)

        results = pd.DataFrame(index=self.g500_data.years)

        results["Only SBTi intensive ($n=8$)"] = self.sbti_data.get_from_emissions("S1", intensive).sum()
        results["Only SBTi intensive ($n=8$)"] += self.sbti_data.get_from_emissions("S2", intensive).sum()
        results["Only SBTi other ($n=36$)"] = self.sbti_data.get_from_emissions("S1", sbti_no_intensive).sum()
        results["Only SBTi other ($n=36$)"] += self.sbti_data.get_from_emissions("S2", sbti_no_intensive).sum()
        results["SBTi other and RE100 ($n=26$)"] = self.sbti_data.get_from_emissions("S1", overlap).sum()
        results["SBTi other and RE100 ($n=26$)"] += self.sbti_data.get_from_emissions("S2", overlap).sum()
        results["Only RE100 ($n=32$)"] = self.re100_data.get_from_emissions("S1", re100_only).sum()
        results["Only RE100 ($n=32$)"] += self.re100_data.get_from_emissions("S2", re100_only).sum()
        results = results / 10**6

        colors = ["black", "grey", "#CC79A7", "#009E73"]
        results.plot.area(ax=ax, rot=0, linewidth=0, legend=None, color=colors, alpha=0.8)

        return ax

    def table_sbti_abs_performance(self):
        absolute = self.idx_sbti_abs
        _, _, sbti_targets_df = self.sbti_data.get_sbti_targeted_s12_results(absolute, extend_targets=True)
        n_s1, n_s1_on_track, t_s1, t_s1_on_track = [0, 0, 0, 0]
        t_mb, n_mb, t_mb_on_track, n_mb_on_track = [0, 0, 0, 0]
        t_lb, n_lb, t_lb_on_track, n_lb_on_track = [0, 0, 0, 0]
        for i in self.idx_sbti_abs:
            target_type = self.sbti_data.target_s12_tco2e.loc[i, "scope"]
            s1 = self.sbti_data.emissions.loc[i, 'S1 2019']
            n_s1 += 1
            t_s1 += s1
            if target_type == "S1+2 LB":
                s2 = self.sbti_data.emissions.loc[i, 'S2 LB 2019']
                t_lb += s2
                n_lb += 1
                if s1+s2 <= sbti_targets_df.loc[i, 2019]:
                    t_s1_on_track += s1
                    n_s1_on_track += 1
                    t_lb_on_track += s2
                    n_lb_on_track += 1
            elif target_type == "S1+2 MB":
                s2 = self.sbti_data.emissions.loc[i, 'S2 MB 2019']
                t_mb += s2
                n_mb += 1
                if s1+s2 <= sbti_targets_df.loc[i, 2019]:
                    t_s1_on_track += s1
                    n_s1_on_track += 1
                    t_mb_on_track += s2
                    n_mb_on_track += 1
            else:
                raise ValueError("The target for this company has an unknown configuration:", i)

        table = pd.DataFrame(index=["S1", "LB", "MB"])
        table.loc["S1", "n"] = n_s1
        table.loc["S1", "on track n"] = n_s1_on_track
        table.loc["S1", "on track n %"] = n_s1_on_track / n_s1
        table.loc["S1", 't'] = t_s1 / 10 ** 6
        table.loc["S1", "on track t"] = t_s1_on_track / 10 ** 6
        table.loc["S1", "on track t %"] = t_s1_on_track / t_s1

        table.loc["LB", "n"] = n_lb
        table.loc["LB", "on track n"] = n_lb_on_track
        table.loc["LB", "on track n %"] = n_lb_on_track/n_lb
        table.loc["LB", 't'] = t_lb / 10**6
        table.loc["LB", "on track t"] = t_lb_on_track / 10**6
        table.loc["LB", "on track t %"] = t_lb_on_track / t_lb

        table.loc["MB", "n"] = n_mb
        table.loc["MB", "on track n"] = n_mb_on_track
        table.loc["MB", "on track n %"] = n_mb_on_track / n_mb
        table.loc["MB", 't'] = t_mb / 10**6
        table.loc["MB", "on track t"] = t_mb_on_track / 10**6
        table.loc["MB", "on track t %"] = t_mb_on_track / t_mb

        print(table)

    def table_sbti_int_performance(self):
        intensity = self.idx_sbti_int
        magnitude = self.g500_plotter.MAGNITUDE
        n_s1, t_s1 = [0, 0]
        n_lb, t_lb = [0, 0]
        n_mb, t_mb = [0, 0]
        s1 = self.sbti_data.get_from_emissions('S1', intensity)
        s2 = self.sbti_data.get_from_emissions('S2', intensity)
        s2_mb = self.sbti_data.get_from_emissions('S2 MB', intensity)
        s2_lb = self.sbti_data.get_from_emissions('S2 LB', intensity)
        for i in intensity:
            n_s1 += 1
            t_s1 += s1.loc[i, 2019]
            if s2.loc[i, 2019] == s2_mb.loc[i, 2019]:
                n_mb += 1
                t_mb += s2.loc[i, 2019]
            elif s2.loc[i, 2019] == s2_lb.loc[i, 2019]:
                n_lb += 1
                t_lb += s2.loc[i, 2019]
            else:
                raise ValueError("S2 value did not match neither LB or MB for company", i)

        print("SBTi intensity")
        print("n S1", n_s1, "t S1", t_s1 / magnitude)
        print("n MB", n_mb, "t MB", t_mb/magnitude)
        print("n LB", n_lb, "t LB", t_lb/magnitude)

    def table_re100_performance(self):
        magnitude = self.g500_plotter.MAGNITUDE
        re100_index = self.idx_re100

        total, actual, target_ratios = self.re100_data.get_re100_targeted_results(re100_index, extend_targets=False)
        actual = actual / magnitude
        targeted = total * target_ratios / magnitude

        n = len(re100_index)
        n_on_track = sum(1 for i in re100_index if actual.loc[i, 2019] >= targeted.loc[i, 2019])
        t = sum(actual[2019])
        t_on_track = 0
        t_on_track = sum([actual.loc[i, 2019] for i in re100_index if actual.loc[i, 2019] >= targeted.loc[i, 2019]])

        print("RE100")
        print("Total", n, "On track", n_on_track, "%", n_on_track/n)
        print("Total renewable", t, "Total on track", t_on_track, "%", t_on_track/t)

    def table_scope_contribution(self, index):
        s1 = self.g500_data.get_from_emissions("S1", index)
        s2 = self.g500_data.get_from_emissions("S2", index)
        s2_mb = self.g500_data.get_from_emissions("S2 MB", index)
        s2_lb = self.g500_data.get_from_emissions("S2 LB", index)

        total = pd.DataFrame(index=["S1", "S2 LB", "S2 MB"], columns=self.g500_data.years).fillna(0)
        for i in index:
            for y in self.g500_data.years:
                total.loc["S1", y] += s1.loc[i, y]
                if s2.loc[i, y] == s2_mb.loc[i, y]:
                    total.loc["S2 MB", y] += s2_mb.loc[i, y]
                elif s2.loc[i, y] == s2_lb.loc[i, y]:
                    total.loc["S2 LB", y] += s2_lb.loc[i, y]
                else:
                    raise ValueError("Scope 2 did not match any value for company", i, y)

        total = total / 10**6
        print(total)
        return total

def generate_ncc_pictures():
    """
    Creates all plots in the NCC paper, saving them to the Downloads folder.
    :return:
    """
    plotter = NCCPlots()

    plotter.plot_participants_sector_region()
    plt.savefig(PATH+'participants.pdf')

    print("Table for SBTi \n\n")
    print(plotter.table_sbti_data())
    print("---------------")

    plotter.plot_sbti_ambition2()
    plt.savefig(PATH+"sbti_ambition.pdf")

    plotter.plot_sbti_ambition2(ipcc_region="World")
    plt.savefig(PATH + "sbti_ambition World.pdf")

    plotter.plot_re100_ambition(ipcc_region="R5OECD90+EU")
    plt.savefig(PATH+"re100_ambition.pdf")

    plotter.plot_re100_ambition(ipcc_region="World")
    plt.savefig(PATH + "re100_ambition World.pdf")

    plotter.plot_robustness()
    plt.savefig(PATH+"robustness.pdf")

    plotter.plot_implementation()
    plt.savefig(PATH+"implementation.pdf")

    plotter.plot_substantive()
    plt.savefig(PATH+"substantive.pdf")

    plotter.plot_normalized_e_factors()
    plt.savefig(PATH+"deviation.pdf")

    print("---------------")


test = NCCPlots()
test.g500_plotter.plot_energy(test.idx_re100_only)
