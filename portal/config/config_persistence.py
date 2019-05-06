import logging
import os

from flask import current_app

from .config import SITE_CFG
from .model_persistence import ModelPersistence


class ConfigPersistence(ModelPersistence):

    def __init__(self, target_dir):
        super(ConfigPersistence, self).__init__(
            model_class=None, target_dir=target_dir)

    def import_(self, keep_unmentioned=None):
        data = self.__read__()
        self.__verify_header__(data)

        cfg_file = os.path.join(current_app.instance_path, SITE_CFG)
        if len(data['entry']) != 1:
            raise ValueError(
                "only expecting single {} as an entry in {}".format(
                    SITE_CFG, self.filename))
        cfg_data = data['entry'][0]
        if cfg_data.get('resourceType') != SITE_CFG:
            raise ValueError(
                "didn't find expected 'resourceType': {}".format(
                    SITE_CFG))
        if not os.access(cfg_file, os.W_OK):
            logging.warning("Can't write config to {}, skipping".format(
                cfg_file))
            return
        with open(cfg_file, 'w') as fp:
            for line in cfg_data['results']:
                fp.write(line)

    def serialize(self):
        cfg_file = os.path.join(current_app.instance_path, SITE_CFG)
        with open(cfg_file, 'r') as fp:
            results = [line for line in fp.readlines()]
        # Package like all other resourceType bundles
        return [{"resourceType": SITE_CFG, "results": results}]


def export_config(target_dir):
    config_persistence = ConfigPersistence(target_dir=target_dir)
    return config_persistence.export()


def import_config(target_dir):
    config_persistence = ConfigPersistence(target_dir=target_dir)
    config_persistence.import_()
