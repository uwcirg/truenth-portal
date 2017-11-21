from flask import current_app
import os

from .config import SITE_CFG
from .model_persistence import ModelPersistence


class ConfigPersistence(ModelPersistence):

    def __init__(self):
        super(ConfigPersistence, self).__init__(None)

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
        with open(cfg_file, 'w') as fp:
            for line in cfg_data['results']:
                fp.write(line)

    def serialize(self):
        cfg_file = os.path.join(current_app.instance_path, SITE_CFG)
        with open(cfg_file, 'r') as fp:
            results = [line for line in fp.readlines()]
        # Package for inclusion
        d = {"resourceType": SITE_CFG,
             "results": results}
        return d


def export_config(target_dir):
    config_persistence = ConfigPersistence()
    return config_persistence.export(target_dir=target_dir)


def import_config():
    config_persistence = ConfigPersistence()
    config_persistence.import_()


