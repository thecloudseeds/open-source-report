def CheckMissing(df):
    missing = df.isna().sum().sort_values(ascending = False)
    missing = missing[missing > 0]
    if missing.sum() != 0: 
        missing_percent = missing / len(df) * 100

        missing_df = pd.DataFrame({
            'Feature': missing.index,
            'NumMissing': missing.values,
            'PercentMissing':missing_percent.values,
            'NumUnique': df[missing.index].nunique().values,
            'MostCommon': df[missing.index].mode().iloc[0].values
        })
        return missing_df
    else: 
        print("Dataset has No Nulls")
        return 0

def DescriptiveStats(df):
    stats_df = df.describe(include = 'all').transpose()
    stats_df['skewness'] = np.nan
    stats_df['kurtosis'] = np.nan
    for col in df.select_dtypes([np.number]).columns.to_list():

        stats_df.loc[col,'unique'] = df[col].nunique()
        stats_df.loc[col,'top'] = df[col].mode()[0]
        stats_df.loc[col,'freq'] = df[col].value_counts().values[0]
        stats_df.loc[col,'skewness'] = df[col].skew()
        stats_df.loc[col,'kurtosis'] = df[col].kurtosis()
   
    return stats_df