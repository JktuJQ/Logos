# Logos — knowledge graph for mathematical textbooks

Logos turns mathematical textbooks and problem books into a searchable knowledge graph.
It identifies mathematical objects and the relations between them,
while preserving links to the passages from which they were extracted.

A typical workflow is to ingest a chapter,
search for a theorem,
inspect its statement and proof,
follow a reference to a lemma,
and locate the corresponding passages in the original book.

## Scope

The project processes mathematical books in PDF form,
including digitally typeset documents and scanned pages.
It focuses on definitions, theorems, lemmas, proofs, and exercises.
Ordinary prose provides context for extraction and reference resolution.

The graph connects proofs to the statements they prove
and records explicit references between mathematical objects.
Each object and relation should retain evidence from the source.
Ambiguous or missing reference targets should remain unresolved
until enough information is available to resolve them.

A graph database is a possible home for the knowledge graph.
Text search and vector search may provide complementary ways to discover objects:
for example, by an exact label or phrase,
or by semantic similarity to a query.
The choice of storage, search technology, and other implementation details
will be made as the project develops.

## Pipeline

### Extract source content

Parse each document into an ordered representation of its content,
including text, formulas, and structural information where available.
Use OCR when needed for scanned pages.
Preserve the original document and raw extraction output,
so later processing can be inspected and repeated.

Each extracted block should have an identity and a source location.
Record the PDF page index and bounding boxes where available,
and distinguish printed page numbers from PDF page indices.

### Recover mathematical objects

Identify the type, label, and boundaries of each mathematical object.
Extraction must account for imperfect document parsing:
a block may contain both prose and the beginning of a theorem,
a theorem may span several blocks and contain formulas,
and a proof may continue onto another page.

Represent objects through ordered references to source spans,
so their content can be reconstructed and traced back to the extraction output.
Finding object boundaries and assigning object types are distinct tasks
and should be assessed separately.

A structural baseline can use headings, numbering, and reading order.
Model-based approaches can use surrounding context to identify objects and their boundaries.
Their output should be validated against the source representation,
so that reconstructed content remains traceable.

### Resolve references and build the graph

Collect objects and their printed labels,
then identify references and resolve them using type, number, and scope.
Account for repeated numbering within a book.
Preserve the source passage for every reference,
including those that cannot be resolved confidently.

Attach proofs to statements using explicit wording and document structure.
Keep proofs as separate objects,
so the graph can distinguish a proof's relationship to its statement
from references that occur within the proof.
Explicit references, inferred mathematical dependencies, and thematic similarities
are different kinds of relationships and should remain distinguishable.

### Store and explore

Validate and store objects, source spans, references, and graph relations.
Keep the outputs of extraction, object recovery, and linking independently available,
so downstream stages can be revised without repeating all earlier work.
Record processing configuration and versions for reproducibility.
Repeated processing should avoid unnecessary duplicates,
and failures should leave previous results usable.

Provide ways to ingest documents, search for objects, and inspect them.
Inspection should show an object's content, related objects, and source locations.
Search may combine exact matching with semantic retrieval.

## Development and evaluation

Choose a development corpus and define annotation rules for object types,
boundaries, proof attachments, and explicit references.
Include unnumbered objects, display formulas, imperfect block splits,
and proofs that cross pages.
Evaluate on material from another book with a different layout,
to assess how well the pipeline generalizes.

Build an end-to-end example early,
using manually annotated objects and relations where helpful.
Use it to check that source locations, object boundaries, and graph relationships
can represent the cases found in actual books.
Then automate the stages and compare approaches on the same annotated data.

Measure object detection with precision and recall,
and report type accuracy and boundary agreement separately.
For graph construction, distinguish missed mentions, wrong targets,
and unresolved references.
Evaluate linking on both manually annotated and automatically extracted objects,
to understand how segmentation errors affect the graph.
Distinguish content lost during document parsing
from content present in the extraction output but assigned to the wrong object.

The project should ultimately provide a reproducible pipeline,
a searchable knowledge graph with traceable source evidence,
annotated evaluation material, and an account of its quality and limitations.
Cross-book concept matching, inferred dependencies,
and integration with other mathematical tools are potential directions for development.
