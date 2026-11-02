import numpy as np

from allfather.rank.ltr import project_folds


def test_project_folds_keep_each_project_whole_and_cover_every_query():
    qids = ["a__a-1", "a__a-2", "a__a-3", "b__b-1", "b__b-2", "c__c-1"]
    folds = project_folds(qids, 2)
    tested = np.concatenate([test for _, test in folds])
    assert sorted(tested.tolist()) == list(range(len(qids)))
    for train, test in folds:
        assert not set(train) & set(test)
        projects = {qids[i].rsplit("-", 1)[0] for i in test}
        assert all(qids[i].rsplit("-", 1)[0] not in projects for i in train)


def test_one_fold_per_project_when_asked_for_as_many():
    qids = ["a__a-1", "b__b-1", "b__b-2", "c__c-9"]
    assert len(project_folds(qids, 3)) == 3
