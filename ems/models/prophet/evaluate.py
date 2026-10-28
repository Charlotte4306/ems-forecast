"""Common metrics and plots on identical evaluation timestamps."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


from ems.evaluation import compute_metrics


def plot_predictions(frame, output_dir):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    first = frame.iloc[:336]
    axes[0].plot(first.ds, first.y, label="Actual", linewidth=1)
    axes[0].plot(first.ds, first.yhat, label="Prophet", linewidth=1)
    axes[0].set(title="Prophet: first 14 days of test", ylabel="Calls/hour")
    axes[0].legend()
    axes[1].hist(frame.y - frame.yhat, bins=60)
    axes[1].set(xlabel="Actual - predicted", ylabel="Hours", title="Test residuals")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "predictions.png", dpi=150)
    plt.close(fig)
