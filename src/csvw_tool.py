import logging

try:
    # git install
    from converter.csvw import CSVWConverter, build_schema, EXTENSIONS
except ImportError:
    # pip install
    from cow_csvw.converter.csvw import CSVWConverter, build_schema, EXTENSIONS
import os
import datetime
import argparse
import sys
import traceback
from glob import glob
from rdflib import ConjunctiveGraph
from werkzeug.utils import secure_filename


logger = logging.getLogger(__name__)

class COW(object):

    def __init__(self, mode=None, files=None, dataset=None, delimiter=None, quotechar='\"', processes=4, chunksize=5000, base="https://iisg.amsterdam/", output_format='nquads', headers = [], verbose = False, strip_whitespace = False):
        """
        COW entry point
        """

        for source_file in files:
            if mode == 'build':
                print("Building schema for {}".format(source_file))
                target_file = "{}-metadata.json".format(source_file)

                if os.path.exists(target_file):
                    modifiedTime = os.path.getmtime(target_file)
                    timestamp = datetime.datetime.fromtimestamp(modifiedTime).isoformat()
                    os.rename(target_file, secure_filename(target_file+"_"+timestamp))
                    print("Backed up prior version of schema to {}".format(target_file+"_"+timestamp))

                build_schema(source_file, target_file, dataset_name=dataset, delimiter=delimiter, quotechar=quotechar, base=base, headers=headers)

            elif mode == 'convert':
                print("Converting {} to RDF".format(source_file))

                try:
                    c = CSVWConverter(source_file, delimiter=delimiter, quotechar=quotechar, processes=processes, chunksize=chunksize, output_format=output_format, verbose = verbose, strip_whitespace = strip_whitespace)
                    c.convert()

                    # >> RH: No idea why this is here, this is already covered by the CSVWConverter code. You're essentially
                    # >> reloading and serializing the same file twice?
                    #
                    # # We convert the output serialization if different from nquads
                    # if output_format not in ['nquads']:
                    #     with open(source_file + '.' + 'nq', 'rb') as nquads_file:
                    #         g = ConjunctiveGraph()
                    #         g.parse(nquads_file, format='nquads')
                    #     # We serialize in the requested format
                    #     with open(source_file + '.' + EXTENSIONS[output_format], 'w') as output_file:
                    #         output_file.write(g.serialize(format=output_format))

                except ValueError:
                    raise
                except:
                    print("Something went wrong, skipping {}.".format(source_file))
                    traceback.print_exc(file=sys.stdout)
            else:
                print("Whoops for file {}".format(f))

def main():
    parser = argparse.ArgumentParser(description="Not nearly CSVW compliant schema builder and RDF converter")
    parser.add_argument('mode', choices=['convert','build'], default='convert', help='Use the schema of the `file` specified to convert it to RDF, or build a schema from scratch.')
    parser.add_argument('files', metavar='file', nargs='+', type=str, help="Path(s) of the file(s) that should be used for building or converting. Must be a CSV file.")
    parser.add_argument('--dataset', dest='dataset', type=str, help="A short name (slug) for the name of the dataset (will use input file name if not specified)")
    parser.add_argument('--delimiter', dest='delimiter', default=None, type=str, help="The delimiter used in the CSV file(s)")
    parser.add_argument('--quotechar', dest='quotechar', default='\"', type=str, help="The character used as quotation character in the CSV file(s)")
    parser.add_argument('--processes', dest='processes', default='4', type=int, help="The number of processes the converter should use")
    parser.add_argument('--chunksize', dest='chunksize', default='5000', type=int, help="The number of rows processed at each time")
    parser.add_argument('--base', dest='base', default='https://iisg.amsterdam/', type=str, help="The base for URIs generated with the schema (only relevant when `build`ing a schema)")
    parser.add_argument('--format', '-f', dest='format', nargs='?', choices=['trig', 'nquads'], default='nquads', help="RDF serialization format (only supporting concatenation-safe graph-aware formats")
    parser.add_argument('--headers', dest='headers', nargs='*', help="A whitespace separated list of headers (use when the CSV file does not contain header information)")
    parser.add_argument('--verbose', '-v', dest='verbose', action='store_true', default=False, help="Produce verbose output for debugging purposes.")
    parser.add_argument('--strip-whitespace', dest='strip_whitespace', action='store_true', default=False, help="Strip whitespace from cell values prior to processing")

    parser.add_argument('--version', dest='version', action='version', version='x.xx')

    args = parser.parse_args()

    logging.basicConfig()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Set logging to DEBUG")
    else:
        logger.setLevel(logging.INFO)
        logger.info("Set logging to INFO")

    files = []
    for f in args.files:
        files += glob(f)

    logger.debug("Calling CSV On the Web converter...")
    COW(args.mode, files, args.dataset, args.delimiter, args.quotechar, args.processes, args.chunksize, args.base, args.format, args.headers, args.verbose, args.strip_whitespace)
    logger.debug("... done")

if __name__ == '__main__':
    main()