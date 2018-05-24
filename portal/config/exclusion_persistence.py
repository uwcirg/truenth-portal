from .model_persistence import ModelPersistence, require


class ExclusionPersistence(ModelPersistence):
    """Specialized persistence for exclusive handling

    Manages exclusive details needed when replacing settings from one
    database to another.  For example, prior to pulling a fresh copy
    of production, one retains the configuration of the staging interventions
    such that they'll continue to function as previously configured for
    testing.  Otherwise, interventions would need to use production
    values or re-enter staging configuration values to test every time.

    """
    def __init__(
            self, model_class, limit_to_attributes, filter_query,
            target_dir=None, lookup_field='id',):
        super(ExclusionPersistence, self).__init__(
            model_class=model_class,
            lookup_field=lookup_field,
            sequence_name=None,
            target_dir=target_dir)
        self.limit_to_attributes = limit_to_attributes
        self.filter_query = filter_query

    @property
    def query(self):
        """return ready query to obtain correct set of objects to persist"""
        if not self.filter_query:
            return super(ExclusionPersistence, self).query
        return self.filter_query()

    def require_lookup_field(self, obj, serial_form):
        """Include lookup_field when lacking"""
        results = dict(serial_form)

        if isinstance(self.lookup_field, tuple):
            for attr in self.lookup_field:
                require(obj, attr, serial_form)
            return serial_form

        # As the serialization method is often used for FHIR representation
        # and the object may not typically be handled by persistence, for
        # example with Users, force the lookup field into the serialization
        # form if missing.

        if self.lookup_field not in serial_form:
            results[self.lookup_field] = getattr(obj, self.lookup_field)
        return results

    def update(self, new_data):
        """Strip unwanted attributes before delegating to parent impl"""

        if self.limit_to_attributes is None:
            return super(ExclusionPersistence, self).update(new_data)

        keepers = set(self.limit_to_attributes)
        keepers.add(self.lookup_field)
        desired = {k: v for k, v in new_data.items() if k in keepers}
        return super(ExclusionPersistence, self).update(desired)
