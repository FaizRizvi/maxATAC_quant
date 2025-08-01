import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from maxatac.utilities.genome_tools import load_bigwig, chromosome_blacklist_mask, import_prediction_array_fn, import_quant_goldstandard_array_fn
from sklearn import metrics
from sklearn.metrics import precision_recall_curve, r2_score
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from maxatac.utilities.system_tools import remove_tags
import pybedtools
from multiprocessing import Pool
import multiprocessing

'''def process_row(i, dfdf, blacklist_mask, chromosome, chromosome_length, agg_function, bin_count):
    #load_pred = load_bigwig(dfdf.prediction[i])
    #pred_array = import_prediction_array_fn(load_pred, chromosome, chromosome_length, agg_function, bin_count)

    load_quant_gs = load_bigwig(dfdf.gold_standard[i])
    quant_gs_array = import_quant_goldstandard_array_fn(load_quant_gs, chromosome, chromosome_length,
                                                        agg_function, bin_count)

    #pred_array_bl = pred_array[blacklist_mask]
    quant_gs_array_bl = quant_gs_array[blacklist_mask]

    #big_arr = np.array([quant_gs_array_bl, pred_array_bl])

    big_arr = np.array([quant_gs_array_bl])
    temp_df = pd.DataFrame(data=big_arr)

    return temp_df'''

def calculate_sse(vector1, vector2):
    """
    Calculates the sum of squared errors (SSE) between two NumPy vectors.

    Args:
        vector1 (np.ndarray): The first vector.
        vector2 (np.ndarray): The second vector.

    Returns:
        float: The sum of squared errors.
    """
    if vector1.shape != vector2.shape:
        raise ValueError("Vectors must have the same shape.")

    squared_differences = (vector1 - vector2) ** 2
    sse = np.sum(squared_differences)
    return sse

class calculate_R2_pearson_spearman(object):
    """
    Calculate the R2, Pearson, and Spearman Correlation for Quantitative Predictions
    :param prediction_bw: The input prediction bigwig file
    :param gold_standard_bw: The input gold standard file
    :param chromosome: The chromosome to limit the analysis to
    :param results_location: The location to write the results to
    :param blacklist_bw: The blacklist mask that is used to remove bins overlapping blacklist regions

    :return: Writes a TSV for the P/R curve
    """

    def __init__(self,
                 prediction_bw,
                 goldstandard_bw,
                 quant_goldstandard_bw,
                 chromosome,
                 bin_size,
                 agg_function,
                 results_location,
                 blacklist_bw,
                 quant_gs_null
                 ):

        """
        Initialize all input values as part of the Class
        """
        self.results_location = results_location

        self.prediction_stream = load_bigwig(prediction_bw)
        self.goldstandard_stream = load_bigwig(goldstandard_bw)
        self.quant_goldstandard_stream = load_bigwig(quant_goldstandard_bw)
        self.quant_gs_null_stream = load_bigwig(quant_gs_null)

        self.chromosome = chromosome
        self.chromosome_length = self.goldstandard_stream.chroms(self.chromosome)

        self.bin_count = int(int(self.chromosome_length) / int(bin_size))  # need to floor the number
        self.bin_size = bin_size
        self.agg_function = agg_function
        self.quant_gs_null = quant_gs_null # change to quant_null_model

        # This has been modified
        self.blacklist_mask = chromosome_blacklist_mask(blacklist_bw,
                                                        self.chromosome,
                                                        self.chromosome_length,
                                                        self.bin_count)

        '''self.blacklist_mask = chromosome_blacklist_mask(blacklist_bw,
                                                        self.chromosome,
                                                        self.chromosome_length,
                                                        self.chromosome_length #self.bin_count #nBins= bin_size
                                                        )'''

        # Call on the def in the class object to do the calculations
        self.__import_prediction_array__()
        self.__import_goldstandard_array__()
        self.__import_quant_goldstandard_array__()
        self.__import_quant_goldstandard_null_array__()
        self.__R2_Sp_P__()
        self.__plot__()

    def __import_prediction_array__(self):
        """
        Import the chromosome signal from the predictions bigwig file and convert to a numpy array.
        """
        logging.info("Import Predictions Array")

        # Get the bin stats from the prediction array

        self.prediction_array = np.nan_to_num(np.array(self.prediction_stream.stats(self.chromosome,
                                                                                    0,
                                                                                    self.chromosome_length,
                                                                                    type=self.agg_function,
                                                                                    nBins=self.bin_count,
                                                                                    exact=True),
                                                       dtype=float  # need it to have NaN instead of None
                                                       )
                                              )



    def __import_goldstandard_array__(self):
        """
        Import the chromosome signal from the gold standard bigwig file and convert to a numpy array.
        """

        logging.info("Import Gold Standard Array")
        # prediction_chromosome_data = np.round(prediction_chromosome_data, round_predictions)

        # Get the bin stats from the gold standard array

        self.goldstandard_array = np.nan_to_num(np.array(self.goldstandard_stream.stats(self.chromosome,
                                                                                        0,
                                                                                        self.chromosome_length,
                                                                                        type=self.agg_function,
                                                                                        nBins=self.bin_count,
                                                                                        exact=True
                                                                                        ),
                                                         dtype=float  # need it to have NaN instead of None
                                                         )
                                                ) # Commented out to keep values non-boolean:  > 0  # to convert to boolean array


    def __import_quant_goldstandard_array__(self):
        """
        Import the chromosome signal from the gold standard bigwig file and convert to a numpy array.
        """

        logging.info("Import Quantitative Gold Standard Array")
        # prediction_chromosome_data = np.round(prediction_chromosome_data, round_predictions)

        # Get the bin stats from the gold standard array

        self.quant_goldstandard_array = np.nan_to_num(np.array(self.quant_goldstandard_stream.stats(self.chromosome,
                                                                                        0,
                                                                                        self.chromosome_length,
                                                                                        type=self.agg_function,
                                                                                        nBins=self.bin_count,
                                                                                        exact=True
                                                                                        ),
                                                         dtype=float  # need it to have NaN instead of None
                                                         )
                                                ) # Commented out to keep values non-boolean:  > 0  # to convert to boolean array

    def __import_quant_goldstandard_null_array__(self):
        """
        Import the chromosome signal from the gold standard null model bigwig file and convert to a numpy array.
        """

        logging.info("Import Quantitative Gold Standard Null Model as Array")
        # prediction_chromosome_data = np.round(prediction_chromosome_data, round_predictions)

        # Get the bin stats

        self.quant_goldstandard_null_array = np.nan_to_num(np.array(self.quant_gs_null_stream.stats(self.chromosome,
                                                                                                    0,
                                                                                                    self.chromosome_length,
                                                                                                    type=self.agg_function,
                                                                                                    nBins=self.bin_count,
                                                                                                    exact=True
                                                                                                    ),
                                                               dtype=float  # need it to have NaN instead of None
                                                               )
                                                      )  # Commented out to keep values non-boolean:  > 0  # to convert to boolean array

    def __R2_Sp_P__(self):
        """
        Calculate the R2, Pearson, and Spearman Correlation for Quantitative Predictions
        """
        ### dfdf = pd.read_csv(self.pred_gs_meta, sep='\t')
        ### dim = dfdf.shape[0]

        blacklist_mask = self.blacklist_mask  # Assuming this is a member variable
        chromosome = self.chromosome  # Assuming this is a member variable
        chromosome_length = self.chromosome_length  # Assuming this is a member variable
        agg_function = self.agg_function  # Assuming this is a member variable
        bin_count = self.bin_count  # Assuming this is a member variable

        ''''# Using Pool to parallelize the loop
        with Pool(int(multiprocessing.cpu_count())) as pool:
            all_data = pool.starmap(process_row,
                                    [(i, dfdf, blacklist_mask, chromosome, chromosome_length, agg_function, bin_count)
                                     for i in range(dim)])

        # Concatenate the results into a final DataFrame
        all_data_df = pd.concat(all_data)'''


        ''''### Find the Union of all Non-zero Regions for CT_TF prediction and GS
        dfdf = pd.read_csv(self.pred_gs_meta, sep='\t')
        dim = dfdf.shape[0]

        all_data=[]
        for i in range(dim):

            load_pred = load_bigwig(dfdf.prediction[i])
            pred_array = import_prediction_array_fn(load_pred, self.chromosome, self.chromosome_length, self.agg_function,
                                    self.bin_count)

            load_quant_gs = load_bigwig(dfdf.gold_standard[i])
            quant_gs_array = import_quant_goldstandard_array_fn(load_quant_gs, self.chromosome, self.chromosome_length, self.agg_function, self.bin_count)

            pred_array_bl = pred_array[self.blacklist_mask]
            quant_gs_array_bl = quant_gs_array[self.blacklist_mask]

            big_arr = np.array([quant_gs_array_bl, pred_array_bl])
            temp_df = pd.DataFrame(data=big_arr)
            all_data.append(temp_df)

        all_data_df = pd.concat(all_data)
        '''

        '''quant_gold_arr = self.quant_goldstandard_array[self.blacklist_mask]
        pred_arr = self.prediction_array[self.blacklist_mask]

        big_arr = np.array([quant_gold_arr, pred_arr])
        temp_df = pd.DataFrame(data=big_arr)

        # Filtering by all LFC preds greater than 1
        # these are all bins that have value greater than 1 in LFC pred returns true false bool series
        # create a mask
        m1 = temp_df.loc[1] > 1
        mm = ~m1 # complement, all regions that are <= 1

        # finds all bins with a 0 to exclude
        m2 = (all_data_df == 0).any()

        cols_to_drop = mm & m2 # this mask corresponds to all bins that have 0s in the all_data_df and all LFC <= 1 to be removed



        # Vertically concat temp_df (quant_gold arr and pred_array of interest) with all the quant gs and preds df in all_data_df
        big_data_df = pd.concat([temp_df, all_data_df], ignore_index=True)

        # this was the old way to filter # locate cols with 0s to remove
        # Upgrading the way we filter 0s # cols_to_drop = (big_data_df == 0).any()

        filtered_big_data_df = big_data_df.loc[:, ~cols_to_drop]

        tot_bins_print=big_data_df.shape[1]
        tot_bins_drop_print=cols_to_drop[cols_to_drop == True].shape[0]
        tot_bins_after_filter_print=filtered_big_data_df.shape[1]

        logging.info(f"Total bins: {tot_bins_print}")
        logging.info(f"Total bins removed: {tot_bins_drop_print}")
        logging.info(f"Total bins after filtering: {tot_bins_after_filter_print}")

        # locate cols with 0s to remove
        # columns_to_drop = temp_df.columns[(temp_df.iloc[0] == 0)]
        # filtered_temp_df = temp_df.drop(columns=columns_to_drop)

        # columns_to_drop2 = filtered_temp_df.columns[(filtered_temp_df.iloc[1] == 0)]
        # filtered_temp_df2 = filtered_temp_df.drop(columns=columns_to_drop2)

        filtered_quant_gold_arr = filtered_big_data_df.iloc[0].to_numpy()
        filtered_pred_arr = filtered_big_data_df.iloc[1].to_numpy()

        self.filtered_quant_gold_arr = filtered_quant_gold_arr
        self.filtered_pred_arr = filtered_pred_arr

        print(self.filtered_quant_gold_arr.shape, self.filtered_quant_gold_arr)
        print(self.filtered_pred_arr.shape, self.filtered_pred_arr)

        logging.info("Calculate R2")
        R2_score = r2_score(
            filtered_quant_gold_arr,
            filtered_pred_arr
            )

        logging.info("Calculate Pearson Correlation")
        pearson_score, pearson_pval = pearsonr(
            filtered_quant_gold_arr,
            filtered_pred_arr
            )

        logging.info("Calculate Spearman Correlation")
        spearman_score, spearman_pval = spearmanr(
            filtered_quant_gold_arr,
            filtered_pred_arr
            )'''




        logging.info("Calculate R2_pred")
        SSE_pred = calculate_sse(
            self.quant_goldstandard_array[self.blacklist_mask],
            self.prediction_array[self.blacklist_mask])
        SSE_null = calculate_sse(
            self.quant_goldstandard_array[self.blacklist_mask],
            self.quant_goldstandard_null_array[self.blacklist_mask])
        R2_pred = 1 - SSE_pred / SSE_null


        logging.info("Calculate Pearson Correlation")
        pearson_score, pearson_pval = pearsonr(
            self.quant_goldstandard_array[self.blacklist_mask],
            self.prediction_array[self.blacklist_mask]
            )

        logging.info("Calculate Spearman Correlation")
        spearman_score, spearman_pval = spearmanr(
            self.quant_goldstandard_array[self.blacklist_mask],
            self.prediction_array[self.blacklist_mask]
            )



        R2_Sp_P_df = pd.DataFrame([[R2_pred, pearson_score, pearson_pval, spearman_score, spearman_pval]],
                                  columns=['R2_pred', 'pearson', 'pearson_pval', 'spearman', 'spearman_pval'])

        R2_Sp_P_df.to_csv(self.results_location, sep='\t', index=None, float_format='%.6e')

    def __plot__(self):

        ###
        #quant_gold_arr = self.quant_goldstandard_array[self.blacklist_mask]
        #pred_arr = self.prediction_array[self.blacklist_mask]

        #filtered_quant_gold_arr = self.filtered_quant_gold_arr

        #filtered_pred_arr = self.filtered_pred_arr

        # genomic coordinates
        chr_region = pybedtools.BedTool(f"{self.chromosome}\t0\t{self.chromosome_length}\n", from_string=True)
        chr_df = pybedtools.BedTool().window_maker(b=chr_region, w=self.bin_size).to_dataframe()
        if chr_df.tail(1).end.to_numpy()[0] - chr_df.tail(1).start.to_numpy()[0] != self.bin_size:
            chr_df = chr_df.drop(chr_df.index[-1])
        else:
            pass
        plot_df = chr_df.loc[self.blacklist_mask]

        y_pred= self.prediction_array[self.blacklist_mask]
        y_obs= self.quant_goldstandard_array[self.blacklist_mask]

        plot_df['y_pred'] = y_pred
        plot_df['y_obs'] = y_obs

        # plotting figure
        fig, ax = plt.subplots()
        x = plot_df.y_obs
        y = plot_df.y_pred

        # Fit a line of best fit
        (m, b), (SSE,), *_ = np.polyfit(x, y, deg=1, full=True)
        # set y-intercept = 0
        b=0
        from matplotlib.ticker import MaxNLocator
        import matplotlib.ticker as ticker

        # Generate values for the line of best fit
        xseq = np.linspace(min(x) - 1, max(x) + 1, num=100)
        ax.plot(xseq, m * xseq + b, color='r', lw=2.5, label=f'Best Fit: y = {m:.2f}x + {b:.2f}\nSSE = {SSE:.2f}')

        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

        # line y=x
        plt.plot(xseq, xseq, label='y=x', color='lightgray')

        fit_y = m * xseq + b
        line_y = xseq

        # Calculate R2_(y=x) (R2 between the line of best and the line y=x y-values)
        R2_yisx = r2_score(line_y, fit_y)

        ax.scatter(x, y, s=60, alpha=0.0020, label='Data points')

        plt.title("Observed vs Predicted Scatter" + '\n \n')
        plt.xlabel("Observed", size=20)
        plt.ylabel("Predicted", size=20)

        plt.grid(True, linestyle='-', color='gray', alpha=0.5)
        plt.xticks(size=18)
        plt.yticks(size=18)

        plt.minorticks_on()
        plt.grid(which='minor', linestyle=':', linewidth='0.5', color='grey')
        plt.grid(which='major', linestyle='-', linewidth='1', color='grey', alpha=.6)


        plot_location='_'.join([self.results_location.split(".")[0], "scatterPlot.png"])

        fig.savefig(plot_location,
            bbox_inches="tight"
        )

        plot_df_location = '_'.join([self.results_location.split(".")[0], "scatterPlot_df.tsv"])

        logging.info("Saving scatter plot_df")
        plot_df.to_csv(plot_df_location, sep='\t', index=None)

        R2_yisx_Slope_df = pd.DataFrame([[R2_yisx, m]],
                                  columns=['R2_yisx', 'Slope'])
        R2_yisx_Slope_df_location = "_".join(["_".join(self.results_location.split("_")[:-3]), "R2_yisx_Slope_df.tsv"])

        logging.info("Saving R2_yisx")
        R2_yisx_Slope_df.to_csv(R2_yisx_Slope_df_location, sep='\t', index=None, float_format='%.6e')



class ChromosomeAUPRC(object):
    """
    Benchmark maxATAC binary predictions against a gold standard using AUPRC.

    During initialization the following steps will be performed:

    1) Set up run parameters and calculate bins needed
    2) Load bigwig files into np.arrays
    3) Calculate AUPRC stats
    """

    def __init__(self,
                 prediction_bw,
                 goldstandard_bw,
                 blacklist_bw,
                 chromosome,
                 bin_size,
                 agg_function,
                 results_location,
                 round_predictions,
                 plot=False
                 ):
        """
        :param prediction_bw: Path to bigwig file containing maxATAC predictions
        :param goldstandard_bw: Path to gold standard bigwig file
        :param blacklist_bw: Path to blacklist bigwig file
        :param chromosome: Chromosome to benchmark
        :param bin_size: Resolution to bin the results to
        :param agg_function: Method to use to aggregate multiple signals in the same bin
        """
        self.results_location = results_location

        self.prediction_stream = load_bigwig(prediction_bw)
        self.goldstandard_stream = load_bigwig(goldstandard_bw)

        self.chromosome = chromosome
        self.chromosome_length = self.goldstandard_stream.chroms(self.chromosome)

        self.bin_count = int(int(self.chromosome_length) / int(bin_size))  # need to floor the number
        self.bin_size = bin_size

        self.agg_function = agg_function

        self.blacklist_mask = chromosome_blacklist_mask(blacklist_bw,
                                                        self.chromosome,
                                                        self.chromosome_length,
                                                        self.bin_count)

        self.__import_prediction_array__(round_prediction=round_predictions)
        self.__import_goldstandard_array__()
        self.__AUPRC__()

        if plot:
            logging.info("Plotting AUPRC Curves")
            self.__plot()

    def __import_prediction_array__(self, round_prediction=6):
        """
        Import the chromosome signal from the predictions bigwig file and convert to a numpy array.

        :param round_prediction: The number of floating places to round the signal to
        :return: prediction_array: A np.array that has values binned according to bin_count and aggregated according
        to agg_function
        """
        logging.info("Import Predictions Array")

        # Get the bin stats from the prediction array
        self.prediction_array = np.nan_to_num(np.array(self.prediction_stream.stats(self.chromosome,
                                                                                    0,
                                                                                    self.chromosome_length,
                                                                                    type=self.agg_function,
                                                                                    nBins=self.bin_count,
                                                                                    exact=True),
                                                       dtype=float  # need it to have NaN instead of None
                                                       )
                                              )

        self.prediction_array = np.round(self.prediction_array, round_prediction)

    def __import_goldstandard_array__(self):
        """
        Import the chromosome signal from the gold standard bigwig file and convert to a numpy array with True/False
        entries.

        :return: goldstandard_array: A np.array has values binned according to bin_count and aggregated according to
        agg_function. random_precision: The random precision of the model based on # of True bins/ # of genomic bins
        """
        logging.info("Import Gold Standard Array")

        # Get the bin stats from the gold standard array
        self.goldstandard_array = np.nan_to_num(np.array(self.goldstandard_stream.stats(self.chromosome,
                                                                                        0,
                                                                                        self.chromosome_length,
                                                                                        type=self.agg_function,
                                                                                        nBins=self.bin_count,
                                                                                        exact=True
                                                                                        ),
                                                         dtype=float  # need it to have NaN instead of None
                                                         )
                                                ) > 0  # to convert to boolean array

        self.random_precision = np.count_nonzero(self.goldstandard_array[self.blacklist_mask]) / \
                                np.size(self.prediction_array[self.blacklist_mask])

    def __get_true_positives__(self, threshold):
        """
        Get the number of true positives predicted at a given threshold

        :param threshold: The desired value threshold to limit analysis to
        :return: Number of true positives predicted by the model
        """
        # Find the idxs for the bins that are gt/et some threshold
        tmp_prediction_idx = np.argwhere(self.prediction_array >= threshold)

        # Find the bins in the gold standard that match the threshold prediction bins
        tmp_goldstandard_threshold_array = self.goldstandard_array[tmp_prediction_idx]

        # Count the number of bins in the intersection that are True
        return len(np.argwhere(tmp_goldstandard_threshold_array == True))

    def __get_false_positives__(self, threshold):
        """
        Get the number of false positives predicted at a given threshold

        :param threshold: The desired value threshold to limit analysis to
        :return: Number of false positives predicted by the model
        """
        # Find the idxs for the bins that are gt/et some threshold
        tmp_prediction_idx = np.argwhere(self.prediction_array >= threshold)

        # Find the bins in the gold standard that match the thresholded prediction bins
        tmp_goldstandard_threshold_array = self.goldstandard_array[tmp_prediction_idx]

        # Count the number of bins in the intersection that are False
        return len(np.argwhere(tmp_goldstandard_threshold_array == False))

    def __get_bin_count__(self, threshold):
        """
        Get the number of bins from the prediction array that are greater than or equal to some threshold
        """
        return len(self.prediction_array[self.prediction_array >= threshold])

    def __calculate_AUC_per_rank__(self, threshold):
        """
        Calculate the AUC at each rank on the AUPRC curve
        """
        tmp_df = self.PR_CURVE_DF[self.PR_CURVE_DF["Threshold"] >= threshold]

        # If we only have 1 point do not calculate AUC
        if len(tmp_df["Threshold"].unique()) == 1:
            return 0
        else:
            return metrics.auc(y=tmp_df["Precision"], x=tmp_df["Recall"])

    def __AUPRC__(self):
        """
        Calculate the AUPRc for the predictions compared to a gold standard

        This function will perform the following steps:

        1) AUPR analysis. The sklearn documents states that there are 1 extra set of points added to the curve. We
        remove the last point added to the curve.
        2) Calculate the AUC for each threshold for visualization
        3) Generate statistics for each threshold: tp, fp, fn
        4) Write tsv of AUPR file stats

        :return: AUPRC stats as a pandas dataframe
        """
        logging.info("Calculate precision-recall curve for " + self.chromosome)

        self.precision, self.recall, self.thresholds = precision_recall_curve(
            self.goldstandard_array[self.blacklist_mask],
            self.prediction_array[self.blacklist_mask])

        logging.info("Making DataFrame from results")

        # Create a dataframe from the results
        # Issue 54:
        # The sklearn package will add a point at precision=1 and recall=0
        # https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html
        # remove the last point of the array which corresponds to this extra point
        self.PR_CURVE_DF = pd.DataFrame(
            {'Precision': self.precision[:-1], 'Recall': self.recall[:-1], "Threshold": self.thresholds})

        logging.info("Calculate AUPRc for " + self.chromosome)

        # Calculate AUPRc
        self.AUPRC = metrics.auc(y=self.precision[:-1], x=self.recall[:-1])

        self.PR_CURVE_DF["AUPRC"] = self.AUPRC

        # Calculate the total gold standard bins
        logging.info("Calculate Total GoldStandard Bins")

        self.PR_CURVE_DF["Total_GoldStandard_Bins"] = len(np.argwhere(self.goldstandard_array == True))

        # Find the number of non-blacklisted bins in chr of interest
        rand_bins = len(np.argwhere(self.blacklist_mask == True))

        # Random Precision
        self.PR_CURVE_DF['Random_AUPRC'] = self.PR_CURVE_DF['Total_GoldStandard_Bins'] / rand_bins

        # Log2FC
        self.PR_CURVE_DF['log2FC_AUPRC_Random_AUPRC'] = np.log2(self.PR_CURVE_DF["AUPRC"] / self.PR_CURVE_DF["Random_AUPRC"])

        logging.info("Write results for " + self.chromosome)

        # Write the AUPRC stats to a dataframe
        self.PR_CURVE_DF.to_csv(self.results_location, sep="\t", header=True, index=False)


    def __plot(self, cmap="viridis"):
        points = np.array([self.recall, self.precision]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        fig, axs = plt.subplots(1, figsize=(5, 4), dpi=150)

        # Create a continuous norm to map from data points to colors
        norm = plt.Normalize(0, 1)

        lc = LineCollection(segments, cmap=cmap, norm=norm)
        # Set the values used for colormapping
        lc.set_array(self.thresholds)
        lc.set_linewidth(5)
        line = axs.add_collection(lc)
        fig.colorbar(line)
        plt.grid()
        plt.ylim(0, 1)
        plt.xlim(0, 1)
        plt.ylabel("Precision")
        plt.xlabel("Recall")

        plt.savefig(remove_tags(self.results_location, ".tsv") + ".png")
