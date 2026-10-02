F1: amend constitution, in solo projects that 300 cap will not apply to  PRs but to commits, agents can handle commiting by their own writting miningfull commit mesagges, also  implement suggestion a

F2:Move FR-006's split/trim into Phase 4 as part of T022 (or a new T022a), so the MVP can actually parse start/finish. Narrow T028 to just the validation additions (SameEndpoints, CityNotFound wiring/messaging) layered on already-parsed input.
E1: accept manual verification, consistent with feature 001.
E2:Add test_stations_pipeline_and_routing_share_the_identical_normalize_function (assert stations.pipeline.normalize_city_key is routing.normalize.normalize_city_key or equivalent) to T006's scope.