# Performance tests for ClickHouse statistics

## SELECT

| query | none	| tdigest_and_string |	tdigest_granule_and_string	|
| --- | --- | --- | --- |
|SELECT count() FROM {database}.{table} WHERE 100 < u2 AND u2 < 200 AND 100 < u8 AND u8 < 200 AND heavy == 'heavy'	| 0.124527976	| 0.068766057	| **0.065889657**	|
|SELECT count() FROM {database}.{table} WHERE 100 < u2 AND u2 < 200 AND 100 < u8 AND u8 < 1000 AND heavy == 'heavy'	| 0.120759493	| 0.118891269	| **0.067948974**	|
|SELECT count() FROM {database}.{table} WHERE u2 < 100 AND i4 < 100 AND heavy == 'heavy'	| **0.070716207**	| 0.074748758	| 0.071408317	|
|SELECT count() FROM {database}.{table} WHERE u8 < 100 AND i4 < 100 AND heavy == 'heavy'	| **0.06931255**6	| 0.071869293	| 0.070679775	|
|SELECT count() FROM {database}.{table} WHERE u1 = 100 AND i4 = 100 AND heavy == 'heavy'	| 0.068946	| 0.073076555	| **0.068499031**	|
|SELECT count() FROM {database}.{table} WHERE u8 = 100 AND i4 = 100 AND heavy == 'heavy'	| **0.067462347**	| 0.072448778	| 0.068282356	|
|SELECT count() FROM {database}.{table} WHERE u1 = 100 AND u8 = 100 AND heavy == 'heavy'	| 0.139172441	| 0.066755554	| **0.064780802**	|
|SELECT count() FROM {database}.{table} WHERE u1 < 100 AND u2 < 1000 AND heavy == 'heavy' |	0.140457961	| 0.141025463	| **0.11395874** |
|SELECT count() FROM {database}.{table} WHERE s8 = 'clickhouse 42' AND s16 = 'clickhouse 42' AND heavy == 'heavy'	| **0.117386072**	| 0.211844636 |	0.200955227	|
|SELECT count() FROM {database}.{table} WHERE u1 = 42 AND s64 = 'clickhouse 42' AND heavy == 'heavy'	| 0.136139929	| 0.134966624 |	**0.131041719**	|


## INSERT

	none	tdigest	tdigest_granule	string	

	26.633466005325317	68.90089917182922	70.9543309211731	82.48186373710632
