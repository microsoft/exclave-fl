# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging

from exclave.service.aggregation_exclave.aggregation_exclave import AggregationExclave
from utils.weighted_aggregation_helper import WeightedAggregationHelper

class AvgAggregationExclave(AggregationExclave):
    def __init__(
        self,
    ):

        super().__init__()
        self.aggregation_weights = {}
        self.aggregation_helper = WeightedAggregationHelper()

    def reset_aggregation_helper(self):
        if self.aggregation_helper:
            self.aggregation_helper.reset_stats()

    def accept(self, local_weight, contributor_name, contribution_round) -> bool:
        """update aggregator's internal state"""

        if local_weight is None:
            logging.error("no data to accept")
            return False
        
        # aggregate
        weight = float(1.0)
        self.aggregation_helper.add(local_weight, weight, contributor_name, contribution_round)
        logging.info("End Accept")
        return True
    
    def aggregate(self):
        logging.info("Start aggregation")
        aggregated_model = self.aggregation_helper.get_result()
        logging.info("End aggregation")
        return aggregated_model