import pandas as pd

from train import build_model


def test_build_model_predicts_labels():
    params = {"C": 1.0, "max_features": 100, "ngram_max": 1, "random_seed": 42}
    data = pd.DataFrame({"text": ["great movie", "loved it", "terrible film", "boring and bad"], "label": [1, 1, 0, 0]})
    model = build_model(params).fit(data[["text"]], data["label"])
    predictions = model.predict(pd.DataFrame({"text": ["great", "bad"]}))
    assert len(predictions) == 2
    assert set(predictions) <= {0, 1}
