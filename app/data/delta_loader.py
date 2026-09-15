import asyncio
import logging
from functools import partial

import delta_sharing
import pandas as pd

logger = logging.getLogger(__name__)

SHARE = "centercode_share"
SCHEMA = "centercode"
TABLES = [
    "zcc_act_stat",
    "zcc_knt_mstr",
    "zcc_prj_hdr",
    "zcc_prt_mtrc",
    "zcc_ptm_lnk",
    "zcc_qa_sat",
    "zcc_tkt_itm",
    "zcc_usr_mstr",
]


def _load_table(config_path: str, fqn: str, limit: int) -> pd.DataFrame:
    url = f"{config_path}#{fqn}"
    if limit and limit > 0:
        return delta_sharing.load_as_pandas(url, limit=limit)
    return delta_sharing.load_as_pandas(url)


async def load_all_tables(config_path: str, limit: int = 1000) -> dict[str, pd.DataFrame]:
    loop = asyncio.get_event_loop()
    dataframes: dict[str, pd.DataFrame] = {}
    for table in TABLES:
        fqn = f"{SHARE}.{SCHEMA}.{table}"
        logger.info("Loading table %s ...", table)
        fn = partial(_load_table, config_path, fqn, limit)
        df = await loop.run_in_executor(None, fn)
        logger.info("  → %d rows, %d columns", len(df), len(df.columns))
        dataframes[table] = df
    return dataframes
