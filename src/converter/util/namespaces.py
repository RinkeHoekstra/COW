from rdflib import RDF, RDFS, OWL, XSD, Namespace

BIBO = Namespace("http://purl.org/ontology/bibo/")
BIO = Namespace("http://purl.org/vocab/bio/0.1/")
CSVW = Namespace("http://www.w3.org/ns/csvw#")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
LDP = Namespace("http://www.w3.org/ns/ldp#")
PROV = Namespace("http://www.w3.org/ns/prov#")
QB = Namespace("http://purl.org/linked-data/cube#")
SCHEMA = Namespace("http://schema.org/")
SDMX_CODE = Namespace("http://purl.org/linked-data/sdmx/2009/code#")
SDMX_CONCEPT = Namespace("http://purl.org/linked-data/sdmx/2009/concept#")
SDMX_DIMENSION = Namespace("http://purl.org/linked-data/sdmx/2009/dimension#")
SDMX_MEASURE = Namespace("http://purl.org/linked-data/sdmx/2009/measure#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
TIME = Namespace("http://www.w3.org/2006/time#")
XML = Namespace("http://www.w3.org/XML/1998/namespace/")
NP = Namespace("http://www.nanopub.org/nschema#")

COW = Namespace("https://iisg.nl/cow/")


PREFIXES = {
    "bibo": BIBO,
    "bio": BIO,
    "csvw": CSVW,
    "dct": DCT,
    "foaf": FOAF,
    "ldp": LDP,
    "owl": OWL,
    "prov": PROV,
    "qb": QB,
    "schema": SCHEMA,
    "sdmx-code": SDMX_CODE,
    "sdmx-concept": SDMX_CONCEPT,
    "sdmx-dimension": SDMX_DIMENSION,
    "sdmx-measure": SDMX_MEASURE,
    "skos": SKOS,
    "xml": XML,
    "time": TIME,
    "np": NP,
    "cow": COW
}