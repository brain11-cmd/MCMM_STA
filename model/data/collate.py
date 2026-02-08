"""
Collate function for STADataset.

batch_size=1 for graph data (each sample is a full graph).
"""

from data.dataset import STASample


def collate_sta(batch):
    """Identity collate: batch_size must be 1, return the single STASample."""
    assert len(batch) == 1, (
        f"STADataset requires batch_size=1 (got {len(batch)}). "
        f"Each sample is a full graph — batching requires graph merging."
    )
    return batch[0]
