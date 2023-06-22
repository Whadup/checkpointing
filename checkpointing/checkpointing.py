import inspect
import json
import dill
import io
import os
import hashlib
import logging
def load_cache():
    if not os.path.exists(".cache"):
        os.mkdir(".cache")
        return {}
    files = os.listdir(".cache")
    cache = set()
    for fname in files:
        if fname.endswith(".pickle"):
            cache.add(int(fname[:-len(".pickle")]))
    logging.debug(f"Loaded cache: {cache}")
    return cache


_CACHE = load_cache()
_CACHED_OBJECTS_obj2key = {}
_CACHED_OBJECTS_key2obj = {}

def hash(bytes_obj):
    return int.from_bytes(hashlib.sha256(bytes_obj).digest()[:8], 'little')

def safe_hash(obj):
    try:
        h = obj.__hash__()
    except:
        h = id(obj)
    return h

class CheckpointPlaceholder:
    def __init__(self, key):
        self.key = key
    # override equality check and hash function
    def __eq__(self, other):
        return self.key == other.key
    def __hash__(self):
        return self.key

def iterate_and_store_native_types(obj):
    if obj is None:
        pass
    elif isinstance(obj, dict):
        try:
            json.dumps(obj)
        except:
            obj = dict({iterate_and_store_native_types(k):iterate_and_store_native_types(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        try:
            json.dumps(obj)
        except:
            obj = list([iterate_and_store_native_types(v) for v in obj])
    elif isinstance(obj, tuple):
        try:
            json.dumps(obj)
        except:
            obj = tuple([iterate_and_store_native_types(v) for v in obj])
    else:
        # check if object is a class instance and if we can find the source code for the class
        class_hash = 0
        try:
            source = inspect.getsource(obj.__class__)
            class_hash = hash(source.encode())
        except:
            pass
        #use dill to store object
        # Construct a key for the object ba
        with io.BytesIO() as f:
            dill.dump(obj, f)
            f.seek(0)
            object_hash = hash(f.getvalue())
            key = class_hash + object_hash
            f.seek(0)
            with open(f".cache/{key}.pickle", "wb") as outfile:
                outfile.write(f.getvalue())
            with open(f".cache/{key}.json", "w") as outfile:
                json.dump({"class_hash":class_hash, "object_hash":object_hash}, outfile)
            _CACHED_OBJECTS_obj2key[safe_hash(obj)] = key
            _CACHED_OBJECTS_key2obj[key] = obj
            # _CACHE[key] = cache_key 
        obj = CheckpointPlaceholder(key)
    return obj

def recursively_replace_objects_with_keys(obj):
    if obj is None:
        pass
    elif isinstance(obj, dict):
        try:
            json.dumps(obj)
        except:
            obj = dict({recursively_replace_objects_with_keys(k):recursively_replace_objects_with_keys(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        try:
            json.dumps(obj)
        except:
            obj = list([recursively_replace_objects_with_keys(v) for v in obj])
    elif isinstance(obj, tuple):
        try:
            json.dumps(obj)
        except:
            obj = tuple([recursively_replace_objects_with_keys(v) for v in obj])
    else:
        logging.debug("check if argument is in cache")
        logging.debug(_CACHED_OBJECTS_obj2key)
        if safe_hash(obj) in _CACHED_OBJECTS_obj2key:
            logging.debug(f"Found object in cache {obj} {_CACHED_OBJECTS_obj2key[safe_hash(obj)]}")
            obj = _CACHED_OBJECTS_obj2key[safe_hash(obj)]
        else:
            obj = safe_hash(obj)

    return obj

def recursively_replace_key_with_objects(obj):
    if obj is None:
        return None
    elif isinstance(obj, dict):
        obj = dict({recursively_replace_key_with_objects(k):recursively_replace_key_with_objects(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        obj = list([recursively_replace_key_with_objects(v) for v in obj])
    elif isinstance(obj, tuple):
        obj = tuple([recursively_replace_key_with_objects(v) for v in obj])
    else:
        if isinstance(obj, CheckpointPlaceholder):
            if obj.key in _CACHED_OBJECTS_key2obj:
                obj = _CACHED_OBJECTS_key2obj[obj.key]
            else:
                logging.debug(f"Loading object from disk: {obj.key}")
                key = obj.key
                with open(f".cache/{obj.key}.pickle", "rb") as f:
                    obj = dill.load(f)
                    _CACHED_OBJECTS_key2obj[key] = obj
                    _CACHED_OBJECTS_obj2key[safe_hash(obj)] = key
                # check if source hash still matches
                # load meta data from json file
                with open(f".cache/{key}.json", "rb") as f:
                    meta = json.load(f)
                    # check if source hash still matches
                    try:
                        source = inspect.getsource(obj.__class__)
                    except:
                        pass
                    else:
                        class_hash = hash(source.encode())
                        if class_hash != meta["class_hash"]:
                            logging.debug(f"comparing class hashes {class_hash} {meta['class_hash']}")
                            raise Exception("Class source code has changed")
    return obj

def replace_objects_with_keys(args, kwargs):
    replaced_args = []
    replaced_kwargs = {}
    replaced_args = list([recursively_replace_objects_with_keys(arg) for arg in args])
    replaced_kwargs = dict({k:recursively_replace_objects_with_keys(v) for k, v in kwargs.items()})
    return replaced_args, replaced_kwargs


def checkpointed_function(func):
    def wrapper(*args, **kwargs):
        # get AST source code of function func
        source = inspect.getsource(func)
        # get hash of source code
        source_hash = hash(source.encode())
        # replace objects in arguments that are in _CACHED_OBJECTS cache with their keys to allow hash matching
        replaced_args, replaced_kwargs = replace_objects_with_keys(args, kwargs)
        # then compute the hash
        logging.debug(replaced_args)
        logging.debug(replaced_kwargs)
        argument_hash = hash(json.dumps({"args":replaced_args, "kwargs":replaced_kwargs}, sort_keys=True).encode())
        combined_hash = source_hash + argument_hash
        logging.debug("Combined hash:", combined_hash, "Source hash:", source_hash, "Argument hash:", argument_hash)
        if combined_hash in _CACHE:
            logging.debug("Found the function in the cache")
            # load result from cached
            obj = dill.load(open(f".cache/{combined_hash}.pickle", "rb"))
            # recursively replace keys with objects
            try:
                logging.debug("LOADED OBJECT FROM CACHE")
                logging.debug(obj)
                logging.debug("=============")
                results = recursively_replace_key_with_objects(obj)
                logging.debug(results)
                logging.debug("=============")
                return results
            except Exception as e:
                logging.debug("Failed to load object from cache, recomputing", e)
        logging.info(f"Exectuing a checkpointed function. {func.__name__}")
        results = func(*args, **kwargs)
        # parse results and put them into cache
        logging.debug("CACHED RESULTS")
        logging.debug(results)
        logging.debug("=============")
        # Store only a Skeleton in the cache, each object is stored separately
        converted = iterate_and_store_native_types(results)
        logging.debug(converted)
        logging.debug("=============")
        # store results in cache
        with open(f".cache/{combined_hash}.pickle", "wb") as outfile:
            dill.dump(converted, outfile)
        return results
    return wrapper

