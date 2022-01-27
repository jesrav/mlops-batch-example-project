from tempfile import TemporaryDirectory
from typing import Type

import joblib
from sklearn.model_selection import cross_val_predict
import wandb
import hydra

from src.models.evaluation import RegressionEvaluation
from src.models import models
from src.utils import read_dataframe_artifact, log_dir, log_file
from src.logger import logger

TARGET_COLUMN = "median_house_price"


def train_evaluate(
    pipeline_class: Type[models.BasePipeline],
    config: dict,
):
    run = wandb.init(project=config["main"]["project_name"], job_type="Cross validation", config=dict(config))

    pipeline = pipeline_class.get_pipeline(**(config["model"]["params"]))

    logger.info("Read training data.")
    df = read_dataframe_artifact(run, "train-validate-data:latest")

    logger.info("predict on hold out data using cross validation.")
    predictions = cross_val_predict(
        estimator=pipeline,
        X=df,
        y=df[TARGET_COLUMN],
        cv=config["evaluation"]["cross_validation_folds"],
        verbose=3,
    )

    model_evaluation = RegressionEvaluation(
        y_true=df[TARGET_COLUMN],
        y_pred=predictions,
    )

    logger.info("train on model on all data")
    pipeline.fit(df, df[TARGET_COLUMN])

    logger.info("Logging performance metrics.")
    run.summary.update(model_evaluation.get_metrics())

    wandb.log(model_evaluation.get_metrics())

    logger.info("Logging model evaluation artifacts.")
    with TemporaryDirectory() as tmpdirname:
        model_evaluation.save_evaluation_artifacts(outdir=tmpdirname)
        log_dir(
            run=run,
            dir_path=tmpdirname,
            type="evaluation-artifacts",
            name="evaluation-artifacts",
            descr="Artifacts created when evaluating model performance"
        )

    logger.info("Logging model trained on all data as an artifact.")
    with TemporaryDirectory() as tmpdirname:
        file_name = tmpdirname + "model.pickle"
        joblib.dump(pipeline, file_name)
        log_file(
           run=run,
           file_path=file_name,
           type="model",
           name="model",
           descr="Trained pipeline"
        )


@hydra.main(config_path="../../conf", config_name="config")
def main(config):
    model_class = getattr(models, config["model"]["model_class"])
    train_evaluate(
        pipeline_class=model_class,
        config=config,
    )


if __name__ == '__main__':
    main()