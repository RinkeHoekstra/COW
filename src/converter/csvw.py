import os
import datetime
import csv
import json
import logging
import iribaker
import traceback
import rfc3987
import multiprocessing as mp
import codecs
from jinja2 import Template
from .util import get_namespaces, Nanopublication, CSVW, PROV, apply_default_namespaces
from rdflib import URIRef, Literal, Graph, BNode, XSD, Dataset
from rdflib.resource import Resource
from rdflib.collection import Collection
from functools import partial
from itertools import zip_longest



logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def build_schema(infile, outfile, delimiter=',', quotechar='\"', encoding='utf-8', dataset_name=None):
    url = os.path.basename(infile)
    # Get the current date and time (UTC)
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    if dataset_name is None:
        dataset_name = url

    metadata = {
        "@context": ["http://www.w3.org/ns/csvw", {"@language": "en", "@base": "http://data.socialhistory.org/ns/resource/"}, get_namespaces()],
        "url": url,
        "dialect": {
             "delimiter": delimiter,
             "encoding": encoding,
             "quoteChar": quotechar
         },
        "dc:title": dataset_name,
        "dcat:keyword": [],
        "dc:publisher": {
            "schema:name": "CLARIAH Structured Data Hub - Datalegend",
            "schema:url": {"@id": "http://datalegend.org"}
        },
        "dc:license": {"@id": "http://opendefinition.org/licenses/cc-by/"},
        "dc:modified": {"@value": today, "@type": "xsd:date"},
        "tableSchema": {
            "columns": [],
            "primaryKey": None,
            "aboutUrl": "{_row}"
        }
    }

    with open(infile, 'r') as infile_file:
        r = csv.reader(infile_file, delimiter=delimiter, quotechar=quotechar)

        header = next(r)

        print(header)

        # First column is primary key
        metadata['tableSchema']['primaryKey'] = header[0]

        for head in header:
            col = {
                "name": head,
                "titles": [head],
                "dc:description": head,
                "datatype": "string"
            }

            metadata['tableSchema']['columns'].append(col)

    with open(outfile, 'w') as outfile_file:
        outfile_file.write(json.dumps(metadata, indent=True))

    logger.info("Done")
    return


class Item(Resource):
    """Wrapper for the rdflib.resource.Resource class that allows getting property values from resources."""
    def __getattr__(self, p):
        """Returns the object for predicate p, either as a list (when multiple bindings exist), as an Item
           when only one object exists, or Null if there are no values for this predicate"""
        try:
            objects = list(self.objects(self._to_ref(*p.split('_', 1))))
        except:
            logger.debug("Calling parent function for Item.__getattr__ ...")
            super(Item, self).__getattr__(self, p)
            # raise Exception("Attribute {} does not specify namespace prefix/qname pair separated by an ".format(p) +
            #                 "underscore: e.g. `.csvw_tableSchema`")

        # If there is only one object, return it, otherwise return all objects.
        if len(objects) == 1:
            return objects[0]
        elif len(objects) == 0:
            return None
        else:
            return objects

    def _to_ref(self, pfx, name):
        """Concatenates the name with the expanded namespace prefix into a new URIRef"""
        return URIRef(self._graph.store.namespace(pfx) + name)


class CSVWConverter(object):

    def __init__(self, file_name, delimiter=',', quotechar='\"', encoding='utf-8', processes=2, chunksize=5):

        self.file_name = file_name
        self.target_file = self.file_name + '.nq'
        schema_file_name = file_name + '-metadata.json'

        self._processes = processes
        self._chunksize = chunksize

        self.np = Nanopublication(file_name)
        # self.metadata = json.load(open(schema_file_name, 'r'))
        self.metadata_graph = Graph()
        with open(schema_file_name) as f:
            self.metadata_graph.load(f, format='json-ld')

        (self.metadata_uri, _) = next(self.metadata_graph.subject_objects(CSVW.url))
        self.metadata = Item(self.metadata_graph, self.metadata_uri)

        # This overrides the identifier of the schema file with that of the nanopublication... do we want that?
        # TODO: No, I don't think so but it creates a disconnect between the publicationInfo and the nanopublication
        # self.metadata['@id'] = self.np.uri

        self.schema = self.metadata.csvw_tableSchema

        # Taking defaults from init arguments
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.encoding = encoding

        # Read csv-specific dialiect specification from JSON structure
        if self.metadata.csvw_dialect is not None:
            if self.metadata.csvw_dialect.csvw_delimiter is not None:
                self.delimiter = str(self.metadata.csvw_dialect.csvw_delimiter)

            if self.metadata.csvw_dialect.csvw_quotechar is not None:
                self.quotechar = str(self.metadata.csvw_dialect.csvw_quoteChar)

            if self.metadata.csvw_dialect.csvw_encoding is not None:
                self.encoding = str(self.metadata.csvw_dialect.csvw_encoding)

        logger.info("Quotechar: {}".format(self.quotechar.__repr__()))
        logger.info("Delimiter: {}".format(self.delimiter.__repr__()))
        logger.info("Encoding : {}".format(self.encoding.__repr__()))
        logger.warning("Only taking encoding, quotechar and delimiter specifications into account...")

        # The metadata schema overrides the default namespace values
        # (NB: this does not affect the predefined Namespace objects!)
        # DEPRECATED
        # namespaces.update({ns: url for ns, url in self.metadata['@context'][1].items() if not ns.startswith('@')})

        # Cast the CSVW column rdf:List into an RDF collection
        self.columns = Collection(self.metadata_graph, BNode(self.schema.csvw_column))

    def convert_info(self):
        results = self.metadata_graph.query("""SELECT ?s ?p ?o
                                               WHERE { ?s ?p ?o .
                                                       FILTER(?p = csvw:valueUrl ||
                                                              ?p = csvw:propertyUrl ||
                                                              ?p = csvw:aboutUrl)}""")

        for (s, p, o) in results:
            # Use iribaker
            escaped_object = URIRef(iribaker.to_iri(str(o)))

            # If the escaped IRI of the object is different from the original, update the graph.
            if escaped_object != o:
                self.metadata_graph.set((s, p, escaped_object))
                # Add the provenance of this operation.
                self.np.pg.add((escaped_object,
                                PROV.wasDerivedFrom,
                                Literal(str(o), datatype=XSD.string)))

        self.np.ingest(self.metadata_graph, self.np.pig.identifier)

        return

    def convert(self):
        logger.info("Starting conversion")

        with open(self.target_file, 'w') as target_file:
            with codecs.open(self.file_name, 'r', encoding=self.encoding) as csvfile:
                logger.info("Opening CSV file for reading")
                reader = csv.DictReader(csvfile, delimiter=self.delimiter, quotechar=self.quotechar)

                logger.info("Starting parsing process")

                if self._processes > 1:
                    self._parallel(reader, target_file)
                else:
                    self._simple(reader, target_file)

            self.convert_info()
            # Finally, write the nanopublication info to file
            target_file.write(self.np.serialize(format='nquads'))

    def _simple(self, reader, target_file):
        c = BurstConverter(self.np.ag.identifier, self.columns, self.schema, self.metadata_graph, self.encoding)
        # Out will contain an N-Quads serialized representation of the converted CSV
        out = c.process(0, reader, 1)
        # We then write it to the file
        target_file.write(out)

    def _parallel(self, reader, target_file):
        # Initialize a pool of processes (default=4)
        pool = mp.Pool(processes=self._processes)
        print("Running with {} processes".format(self._processes))

        # The _burstConvert function is partially instantiated, and will be successively called with
        # chunksize rows from the CSV file
        burstConvert_partial = partial(_burstConvert,
                                       identifier=self.np.ag.identifier,
                                       columns=self.columns,
                                       schema=self.schema,
                                       metadata_graph=self.metadata_graph,
                                       encoding=self.encoding,
                                       chunksize=self._chunksize)

        # The result of each chunksize run will be written to the target file
        try:
            for out in pool.imap(burstConvert_partial, enumerate(grouper(self._chunksize, reader))):
                target_file.write(out)
        except:
            traceback.print_exc()

        # Make sure to close and join the pool once finished.
        pool.close()
        pool.join()


def grouper(n, iterable, padvalue=None):
    "grouper(3, 'abcdefg', 'x') --> ('a','b','c'), ('d','e','f'), ('g','x','x')"
    return zip_longest(*[iter(iterable)] * n, fillvalue=padvalue)


# This has to be a global method for the parallelization to work.
def _burstConvert(enumerated_rows, identifier, columns, schema, metadata_graph, encoding, chunksize):

    try:
        count, rows = enumerated_rows
        c = BurstConverter(identifier, columns, schema, metadata_graph, encoding)

        print(mp.current_process().name, count, len(rows))

        result = c.process(count, rows, chunksize)

        print(mp.current_process().name, 'done')

        return result
    except:
        traceback.print_exc()
        return "ERROR"


class BurstConverter(object):

    def __init__(self, identifier, columns, schema, metadata_graph, encoding):
        self.ds = apply_default_namespaces(Dataset())
        self.g = self.ds.graph(URIRef(identifier))

        self.columns = columns
        self.schema = schema
        self.metadata_graph = metadata_graph
        self.encoding = encoding

        self.templates = {}

        self.aboutURLSchema = self.schema.csvw_aboutUrl

    def process(self, count, rows, chunksize):
        obs_count = count * chunksize

        print("Row: {}".format(obs_count))

        for row in rows:
            for k, v in list(row.items()):
                row[k] = v.decode(self.encoding)

            count += 1
            logger.debug("row: {}".format(count))

            for c in self.columns:

                c = Item(self.metadata_graph, c)
                # default about URL
                s = self.expandURL(self.aboutURLSchema, row)

                try:
                    # Can also be used to prevent the triggering of virtual columns!
                    value = row[str(c.csvw_name)].decode(self.encoding)
                    if len(value) == 0 or value == str(c.csvw_null) or value == str(self.schema.csvw_null):
                        # Skip value if length is zero
                        logger.debug("Length is 0 or value is equal to specified 'null' value")
                        continue
                except:
                    # No column name specified (virtual)
                    pass

                try:
                    if str(c.csvw_virtual) == 'true' and c.csvw_aboutUrl is not None:
                        s = self.expandURL(c.csvw_aboutUrl, row)

                    if c.csvw_valueUrl is not None:
                        # This is an object property

                        p = self.expandURL(c.csvw_propertyUrl, row)
                        o = self.expandURL(c.csvw_valueUrl, row)
                    else:
                        # This is a datatype property

                        if c.csvw_value is not None:
                            value = self.render_pattern(c.csvw_value, row)
                        else:
                            # print s, c.csvw_value, c.csvw_propertyUrl, c.csvw_name, self.encoding
                            value = row[str(c.csvw_name)]

                        # If propertyUrl is specified, use it, otherwise use the column name
                        if c.csvw_propertyUrl is not None:
                            p = self.expandURL(c.csvw_propertyUrl, row)
                        else:
                            if "" in self.metadata_graph.namespaces():
                                propertyUrl = self.metadata_graph.namespaces()[""][str(c.csvw_name)]
                            else:
                                propertyUrl = "http://data.socialhistory.org/ns/resource/{}".format(str(c.csvw_name))

                            p = self.expandURL(propertyUrl, row)

                        if c.csvw_datatype == XSD.string and c.csvw_language is not None:
                            # If it is a string datatype that has a language, we turn it into a
                            # language tagged literal
                            # We also render the lang value in case it is a pattern.
                            o = Literal(value, lang=self.render_pattern(c.csvw_language, row))
                        elif c.csvw_datatype is not None:
                            o = Literal(value, datatype=c.csvw_datatype)
                        else:
                            # It's just a plain literal without datatype.
                            o = Literal(value)

                    # Add the triple to the assertion graph
                    self.g.add((s, p, o))
                except:
                    # print row[0], value
                    traceback.print_exc()

            # We increment the observation (row number) with one
            obs_count += 1

        logger.info("... done")
        return self.ds.serialize(format='nquads')

    # def serialize(self):
    #     trig_file_name = self.file_name + '.trig'
    #     logger.info("Starting serialization to {}".format(trig_file_name))
    #
    #     with open(trig_file_name, 'w') as f:
    #         self.np.serialize(f, format='trig')
    #     logger.info("... done")

    def render_pattern(self, pattern, row):
        # Significant speedup by not re-instantiating Jinja templates for every row.
        if pattern in self.templates:
            template = self.templates[pattern]
        else:
            template = self.templates[pattern] = Template(pattern)

        # TODO This should take into account the special CSVW instructions such as {_row}
        # First we interpret the url_pattern as a Jinja2 template, and pass all column/value pairs as arguments
        rendered_template = template.render(**row)

        try:
            # We then format the resulting string using the standard Python2 expressions
            return rendered_template.format(**row)
        except:
            logger.warning("Could not apply python string formatting to '{}'".format(rendered_template))
            return rendered_template

    def expandURL(self, url_pattern, row, datatype=False):
        url = self.render_pattern(str(url_pattern), row)

        # DEPRECATED
        # for ns, nsuri in namespaces.items():
        #     if url.startswith(ns):
        #         url = url.replace(ns + ':', nsuri)
        #         break

        try:
            iri = iribaker.to_iri(url)
            rfc3987.parse(iri, rule='IRI')
        except:
            raise Exception("Cannot convert `{}` to valid IRI".format(url))


        # print "Baked: ", iri
        return URIRef(iri)
