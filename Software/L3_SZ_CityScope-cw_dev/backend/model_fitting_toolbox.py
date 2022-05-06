import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.metrics import mean_squared_error, median_absolute_error, r2_score

rf_trainning_config = {
    ''
}

def fit_rf_regressor(data_df, target, numerical_regressors,
                     categorical_regressors, dummy_drop_first=False,
                     n_estimators=128, test_size=0.2, refit_on_test_data=True,
                     random_state=1, cv=5, n_iter=512, verbose=1):
    data, features, X, y = prepare_data(data_df, target,
                                        numerical_regressors,
                                        categorical_regressors,
                                        dummy_drop_first)
    X_train, X_test, y_train, y_test = train_test_split(X, y,
                                                        test_size = test_size,
                                                        random_state = random_state)
    rf = RandomForestRegressor(random_state = random_state,
                               n_estimators = n_estimators)
    # Do random search
    maxDepth = list(range(5, 100, 5))  # Maximum depth of tree
    maxDepth.append(None)
    minSamplesSplit = range(2, 42, 5)  # Minimum samples required to split a node
    minSamplesLeaf = range(1, 101, 10)  # Minimum samples required at each leaf node
    max_features = ['auto', 'sqrt', 'log2']

    # Create the grid
    randomGrid = {'max_depth': maxDepth,
                  'min_samples_split': minSamplesSplit,
                  'min_samples_leaf': minSamplesLeaf,
                  'max_features': max_features}

    # Create the random search object
    rfRandom = RandomizedSearchCV(estimator = rf,
                                  param_distributions = randomGrid,
                                  n_iter = n_iter,
                                  cv = cv,
                                  verbose = verbose,
                                  random_state = random_state,
                                  refit = True,
                                  n_jobs = -1)
    rfRandom.fit(X_train, y_train)
    rfWinner = rfRandom.best_estimator_
    rfBestParams = rfRandom.best_params_

    # Report performance
    if verbose >= 1:
        print('\nPerformance:\n'+'='*50)
        pred_train = rfWinner.predict(X_train)
        pred_test = rfWinner.predict(X_test)
        print('Training:\nMSE={:4.4f}, Median AE={:4.4f}, r2={:4.4f}'.format(
            mean_squared_error(y_train, pred_train),
            median_absolute_error(y_train, pred_train),
            r2_score(y_train, pred_train)
        ))
        print('\nTest:\nMSE={:4.4f}, Median AE={:4.4f}, r2={:4.4f}'.format(
            mean_squared_error(y_test, pred_test),
            median_absolute_error(y_test, pred_test),
            r2_score(y_test, pred_test)
        ))
    if refit_on_test_data:
        rfWinner.fit(X, y)
        if verbose >= 1:
            print('\nPerformance after refit (not objective!):\n' + '=' * 50)
            pred_train = rfWinner.predict(X_train)
            pred_test = rfWinner.predict(X_test)
            print('Training:\nMSE={:4.4f}, Median AE={:4.4f}, r2={:4.4f}'.format(
                mean_squared_error(y_train, pred_train),
                median_absolute_error(y_train, pred_train),
                r2_score(y_train, pred_train)
            ))
            print('\nTest:\nMSE={:4.4f}, Median AE={:4.4f}, r2={:4.4f}'.format(
                mean_squared_error(y_test, pred_test),
                median_absolute_error(y_test, pred_test),
                r2_score(y_test, pred_test)
            ))
    return {'model': rfWinner, 'bestParams': rfBestParams, 'features': features}


def prepare_data(data_df, target, numerical_regressors, categorical_regressors, dummy_drop_first=False):
    data = data_df[[target] + numerical_regressors + categorical_regressors]
    data = data.loc[~data[target].isnull()]
    features = numerical_regressors.copy()
    for cat_reg in categorical_regressors:
        new_dummies = pd.get_dummies(data[cat_reg], prefix=cat_reg, drop_first=dummy_drop_first)
        data = pd.concat([data, new_dummies], axis=1)
        features += new_dummies.columns.tolist()
    X = np.array(data[features])
    y = np.array(data[target])
    return data, features, X, y

