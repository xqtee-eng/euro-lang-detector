from src.self_learning import promote_feedback_samples
from src.train import train


def retrain():
    promoted = promote_feedback_samples()
    print(f"Promoted feedback samples: {promoted}")
    profiles = train(kind="retrain", notes=f"Promoted feedback samples: {promoted}")
    return {"promoted": promoted, "profiles": len(profiles)}


if __name__ == "__main__":
    retrain()
