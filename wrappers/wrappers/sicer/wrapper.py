import tempfile
import os
import glob
from snakemake import shell

log = snakemake.log_fmt_shell()
logfile = None
redundancy_threshold = snakemake.params.block.get('redundancy_threshold', snakemake.params.get('redundancy_threshold'))
window_size = snakemake.params.block.get('window_size', snakemake.params.get('redundancy_threshold'))
fragment_size = snakemake.params.block.get('fragment_size', snakemake.params.get('fragment_size'))
effective_genome_fraction = snakemake.params.block.get('effective_genome_fraction', snakemake.params.block.get('reference_effective_genome_fraction'))
gap_size = snakemake.params.block.get('gap_size', snakemake.params.get('gap_size'))
fdr = snakemake.params.block.get('fdr', snakemake.params.get('fdr'))
genome_build = snakemake.params.block.get('genome_build', snakemake.params.block.get('reference_genome_build'))

if redundancy_threshold is None:
    raise ValueError("SICER requires the specification of a 'redundancy_threshold'")
if window_size is None:
    raise ValueError("SICER requires the specification of a 'window_size'")
if fragment_size is None:
    raise ValueError("SICER requires the specification of a 'fragment_size'")
if effective_genome_fraction is None:
    raise ValueError("SICER requires the specification of an 'effective_genome_fraction'")
if gap_size is None:
    raise ValueError("SICER requires the specification of a 'gap_size'")
if fdr is None:
    raise ValueError("SICER requires the specification of an 'fdr'")
if genome_build is None:
    raise ValueError("SICER requires the specification of a recognized genome build")

outdir, basebed = os.path.split(snakemake.output.bed)
label = snakemake.params.block['label']

tmpdir = tempfile.mkdtemp()
cwd = os.getcwd()

shell(
    'bamToBed -i {snakemake.input.ip} > {tmpdir}/ip.bed ; '
    'bamToBed -i {snakemake.input.control} > {tmpdir}/in.bed '
)

shell(
    """cd {tmpdir} && """
    """function python {{ $CONDA_PREFIX/bin/python2.7 "$@" ; }} && """
    """SICER.sh {tmpdir} ip.bed in.bed {tmpdir} """
    """{genome_build} {redundancy_threshold} {window_size} """
    """{fragment_size} {effective_genome_fraction} {gap_size} {fdr} && """
    """cd {cwd}"""
)

resultsfile = glob.glob(os.path.join(tmpdir, '*-islands-summary-FDR*'))
if len(resultsfile) == 1:
    hit = resultsfile[0]
    basehit = os.path.basename(resultsfile[0])
elif len(resultsfile) > 1:
    raise ValueError("Multiple islands-summary-FDR files found in temporary working directory: " + str(os.listdir(tmpdir)))
else:
    raise ValueError("No islands-summary-FDR file found: " + str(os.listdir(tmpdir)))

summary_graph = glob.glob(os.path.join(tmpdir, '*-W{0}.graph*'.format(window_size)))
if len(summary_graph) == 1:
    summary_graph = summary_graph[0]
else:
    raise ValueError("SICER graph output file not found")

normalized_prefilter_wig = glob.glob(os.path.join(tmpdir, '*-W{0}-normalized.wig'.format(window_size)))
if len(normalized_prefilter_wig) == 1:
    normalized_prefilter_wig = normalized_prefilter_wig[0]
else:
    raise ValueError("SICER normalized prefilter wig file not found")

candidate_islands = glob.glob(os.path.join(tmpdir, '*-W{0}-G{1}-islands-summary'.format(window_size, gap_size)))
if len(candidate_islands) == 1:
    candidate_islands = candidate_islands[0]
else:
    raise ValueError("SICER candidate islands file not found")

significant_islands = glob.glob(os.path.join(tmpdir, '*-W{0}-G{1}-FDR*-island.bed'.format(window_size, gap_size)))
if len(significant_islands) == 1:
    significant_islands = significant_islands[0]
else:
    raise ValueError("SICER significant islands file not found")

redundancy_removed = glob.glob(os.path.join(tmpdir, '*-W{0}-G{1}-FDR*-islandfiltered.bed'.format(window_size, gap_size)))
if len(redundancy_removed) == 1:
    redundancy_removed = redundancy_removed[0]
else:
    raise ValueError("SICER redundancy removed library file not found")

normalized_postfilter_wig = glob.glob(os.path.join(tmpdir, '*-W{0}-G{1}-FDR*-islandfiltered-normalized.wig'.format(window_size, gap_size)))
if len(normalized_postfilter_wig) == 1:
    normalized_postfilter_wig = normalized_postfilter_wig[0]
else:
    raise ValueError("SICER normalized postfilter wig file not found")


# Fix the output file so that it conforms to UCSC guidelines
#shell("mv {tmpdir}/tmp.sicer.output {snakemake.output.bed}.sicer.output")
#shell("mv {tmpdir}/tmp.sicer.error {snakemake.output.bed}.sicer.error")

shell(
    "export LC_COLLATE=C; "
    """awk -F"\\t" -v lab={label} """
    """'{{printf("%s\\t%d\\t%d\\t%s_peak_%d\\t%d\\t.\\t%g\\t%g\\t%g\\n", $1, """
    """$2, $3-1, lab, NR, -10*log($6)/log(10), $7, -log($6)/log(10), -log($8)/log(10))}}' """
    "{hit} > {snakemake.output.bed}.tmp && "
    "bedSort {snakemake.output.bed}.tmp {snakemake.output.bed} && "
    "cp {resultsfile} {snakemake.output.bed}-islands-summary-significant && "
    "cp {summary_graph} {snakemake.output.bed}.graph && "
    "cp {normalized_prefilter_wig} {snakemake.output.bed}-normalized-prefilter.wig && "
    "cp {normalized_postfilter_wig} {snakemake.output.bed}-normalized-postfilter.wig && "
    "cp {candidate_islands} {snakemake.output.bed}-islands-summary && "
    "cp {significant_islands} {snakemake.output.bed}-island.bed && "
    "cp {redundancy_removed} {snakemake.output.bed}-islandfiltered.bed && "
    "rm {snakemake.output.bed}.tmp && rm -Rf {tmpdir}"
)
