# DataQuery NL-v3 �� 93/100����汾

������ҵ�ز�ҵ����Ա�ĵ�������Ȼ����������������У��ҵ��ṹ����Ҫʱ���壬�ɹ̶�ָ�깫ʽ�������SQLִ�С���Ŀ¼Ϊ���������������滻�ֿ��Ŀ¼����ʷStreamlit��ʾ��

## �ɹ���汾

| ��֤ | ��� |
|---|---:|
| �̶�100����������ͨ�� | 93/100 |
| 70����ȷ��ѯ�ƻ� | 70/70 |
| �����ֵ���嵥�ط� | 70/70 |

�����汾 `nl-v3-diagnostic100-20261005-1`��qwen3.7-max��˼��������Ԥ��4096����� `nl-v3-fixed-backend-1`��100�����70��ѯ��20���塢10�ܾ���ԭʼ�˹������ж�Ϊ93������2���֡�5ʧ�ܣ����ֲ��������֡�����ڱ����ģ�ͼƻ��ϻطźϳ����ݣ������ṩ����������ж������ڼ�����ⷽ��������ҪAPI Key��

## ������֤

Python 3.11+����ʹ�ñ�׼�⡣�ڱ�Ŀ¼���У�

```shell
python -B verify_release.py
python -B -m unittest discover -p "test_*.py"
```

��һ������У�鷢��ָ�ơ�100���Ӧ��ϵ��ԭ�ж�������70����ѯ��λ��SQL���룬�Լ���������ο������һ���ԡ��������ó������������˹������ж���

��ѡ���ڱ�Ŀ¼������ȫ�鹹�����ݣ���ִ��ֻ���طţ�������ҵ�����ݿ⣩��

```shell
python scripts/generate_synthetic_data.py
python -B verify_release.py --synthetic-db data/generated/commercial_real_estate.sqlite3
```

���������ؽ���Ŀ¼ `data/generated` ��ͬ����ʾ���ݿ⣻��Ҫ���Ŀ¼�����Լ������ݡ�Ĭ����֤��ִ��SQL��������ģ�͡�

## �ļ�����

- `json_resolver.py`��`conversation.py`��ģ�������Լ�������붯�����ߡ�
- `query_plan.py`��`time_scope.py`��Ŀ�ꡢɸѡ��ʱ�䡢���������У�顣
- `business_context.json`��`metric_definitions.json`��ҵ��������ָ��ھ���
- `fixed_backend/compiler.py`���̶�����ʽ��������󶨲�����
- `fixed_backend/reference.py`����������·���Ĳο���������
- `SINGLE_TASK_GOLD_REVIEWED_V1.json`��100�⼰����Gold��
- `evaluation/decisions.json`�������100��ģ�ʹ��������
- `evaluation/judgments.json`�������ж������ɡ�
- `evaluation/backend_results.json`��`expected_query_results.json`��ִ�лطż��ο�ֵ��
- `MANIFEST.json`�������ļ���ԭʼ���ָ�ơ�

�������˺����ļ������Ѳ�����ֽڣ�������ںͱ�Я�ĵ�Ϊ��������֪�������ڰ汾���ˣ�[��������������ʵ��](../../docs/EVALUATION_202610.md)�ֱ𱨸�������������ӳ����á�����������ƾ�ݡ�HTTPԭʼ���������Ŀ¼��
