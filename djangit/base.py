import contextlib
import pygit2
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.utils import DatabaseErrorWrapper
from djangit import compilers, cursor
from djangit import gitly as tree


class GitConnectionOpts(object):
    def max_name_length(self):
        return 255

    def compiler(self, suggestion):
        return getattr(compilers, suggestion)

    def bulk_batch_size(self, fields, objs):
        return 10



class GitConnectionFeatures(object):
    truncates_names = False
    can_rollback_ddl = True
    autocommits_when_autocommit_is_off = False
    interprets_empty_strings_as_nulls = False
    can_combine_inserts_with_and_without_auto_increment_pk = True


class GitValidation(object):
    def check_field(self, field, from_model=None):
        return []


class GitIntrospection(object):
    def table_names(self, cursor):
        try:
            return cursor.branch['tables'].keys()
        except KeyError:
            return []


class GitSchemaEditor(object):
    def __init__(self, cursor, connection):
        self.cursor = cursor
        self.connection = connection

    def create_model(self, model):
        """ Is this even neccesary? """
        key = 'tables/%s/%%s' % model._meta.db_table
        self.cursor.branch[key % 'objects'] = tree.EMPTY
        self.cursor.branch[key % 'indexes'] = tree.EMPTY

    def alter_unique_together(self, content_type, thingies, field_sets):
        assert len(field_sets) == 1
        table = content_type._meta.db_table
        idx_name = ','.join(sorted(field_sets.pop()))
        key = 'tables/%s/indexes/%s' % (table, idx_name)
        self.cursor.branch[key] = tree.EMPTY

    def alter_field(self, from_model, from_field, to_field):
        # TODO: Support null fields. Or not?
        # TODO: Typing?
        pass

    def remove_field(self, from_model, field):
        key = 'tables/%s/objects' % from_model._meta.db_table
        for obj in self.cursor.branch[key]:
            whoadude()


class GitConnection(object):
    def __init__(self, *args):
        self.branch = tree.Branch(*args)
        self.last_tree = self.branch.tree.oid

    def commit(self):
        if self.branch.tree.oid != self.last_tree:
            import traceback
            msg = list(reversed([l.splitlines()[0].split(' in ')[1] for l in traceback.format_stack()]))
            self.branch.commit(','.join(msg))
            self.last_tree = self.branch.tree.oid

    def close(self):
        pass


class MyDatabaseErrorWrapper(DatabaseErrorWrapper):
    def __exit__(self, exc_type, *args):
        if exc_type is not None:
            print exc_type, args
            import six
            return six.reraise(exc_type, *args)


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'git'

    Database = type("Database", (), {
        # TODO: Implement own db exception classes.
        '__getattr__': lambda self, _: type(None)
    })()

    def __init__(self, db, alias):
        super(DatabaseWrapper, self).__init__(db, alias)
        #self.alias = alias
        self.ops = GitConnectionOpts()
        self.validation = GitValidation()
        self.features = GitConnectionFeatures()
        self.introspection = GitIntrospection()
        #self.in_atomic_block = False
        #self.savepoint_ids = []
        #self.closed_in_transaction = False
        self.autocommit = False

    @property
    def queries_logged(self):
        return False

    def get_connection_params(self):
        repo = pygit2.Repository(self.settings_dict['NAME'])
        return (repo, self.settings_dict['BRANCH'])

    def get_new_connection(self, params):
        return GitConnection(*params)

    def init_connection_state(self):
        pass

    def create_cursor(self):
        return cursor.GitCursor(self.connection.branch)

    def _rollback(self):
        print "asked to rollback"
        #assert self.connection.branch.tree.oid == self.autocommit_savepoint

    @property
    def wrap_database_errors(self):
        return MyDatabaseErrorWrapper(self)

    @contextlib.contextmanager
    def schema_editor(self):
        yield GitSchemaEditor(self.cursor(), self)

    def savepoint(self):
        return self.connection.branch.tree.oid

    def _set_autocommit(self, val):
        self.autocommit = val

    """
    def savepoint_commit(self, savepoint_id):
        print "savepoint_commit"
        self.commit()

    def rollback(self):
        import pdb; pdb.set_trace()
        assert False, 'asked to rollback'

    def get_autocommit(self):
        return self.autocommit

    def set_autocommit(self, val):
        print 'set autocommit: %s' % val
        self.autocommit = val

    def prepare_database(self):
        pass

    def check_constraints(self, table_names):
        # TODO: Wat do?
        pass

    @contextlib.contextmanager
    def constraint_checks_disabled(self):
        # todo
        yield

    def close(self):
        pass
    """

