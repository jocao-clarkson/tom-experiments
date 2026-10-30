# revpipe

Batch loaders that move payment-provider exports into the finance warehouse.

## Jobs

| Job | Input | Writes |
| --- | --- | --- |
| `orders` | `orders_*.csv` in `REVPIPE_INPUT_DIR` | `orders`, `daily_revenue.gross_minor` |

Run with `revpipe <job>`. Each job is safe to re-run over the same files.

## Configuration

| Variable | Default |
| --- | --- |
| `REVPIPE_DSN` | required |
| `REVPIPE_INPUT_DIR` | `/data/in` |
| `REVPIPE_DEADLETTER_DIR` | `/data/deadletter` |
| `REVPIPE_BATCH_SIZE` | `500` |

Migrations in `migrations/` are applied by the platform migration runner before deploy. Each job runs as a CronJob defined in `deploy/`.
