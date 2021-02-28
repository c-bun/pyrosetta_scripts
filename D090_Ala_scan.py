from __future__ import print_function

################################################################################
# A GENERAL EXPLANATION

"""
ala_scan.py

THIS SCRIPT WILL NOT WORK WITH PYROSETTA V2.0BETA OR EARLIER!

This script determines the interface of a PDB file with two docked proteins and
performs "alanine scanning" by iteratively mutating each interface residue to
alanine and determining the change in "interaction energy". Other amino acids
than alanine can be used. For convenience, this script is split into several
methods for performing the individual tasks. The "interaction energy" is
determined by creating the mutant, repacking residues near the mutated residue
for the wild-type and mutant, and subtracting the pose score from its score
when separated. An alternate method for calculating "binding energy" is
provided which separates and repacks before comparing scores. When mutating,
the protein backbone is static and nearby residues are repacked. The packing
performed in numerous steps of this protocol is redundant (but provided to allow
methods to function independently). Since Rosetta packing is stochastic, several
trials of this script should be averaged to achieve the best results. Since
Rosetta score does not convert to physical energy, the "ddG" predictions are
purely qualitative.

Instructions:

1) ensure that your PDB file is in the current directory
2) run the script:
    from commandline                        >python D090_Ala_scan.py

    from within python/ipython              [1]: run D090_Ala_scan.py

Author: Evan H. Baugh
    based on an original script by Sid Chaudhury
    edited by Jianqing Xu
    revised and motivated by Robert Schleif

Updated by Boon Uranukul, 6/9/12
Simplified special constant seed initialization ~ Labonte

References:
    Kortemme T. and Baker D. "A simple physical model for binding energy
        hot spots in protein-protein complexes," PNAS 22, 14116-14121 (2002)

    Alexandra Shulman Peleg, Maxim Shatsky, Ruth Nussinov and Haim J. Wolfson,
        "Spatial chemical conservation of hot spot interactions in
        protein-protein complexes," BMC Biology 5 5-43 (2007)

"""

################################################################################
# THE BASIC PROTOCOL, scanning, interface_ddG, mutate_residue

"""
This sample script is setup for usage with
    commandline arguments,
    default running within a python interpreter,
    or for import within a python interpreter,
        (exposing the scanning method)

The method sample_refinement:
1.  creates a pose from the desired PDB file
2.  sets up the docking FoldTree and related parameters
3.  creates ScoreFunctions
        -for defining the Interface
        -for determining "ddG"
4.  creates an Interface object defining the protein-protein interface
5.  creates a PyMOLMover for exporting structures to PyMOL
6.  perform scanning by:
        a. looping over the pose residues, if it is an Interface residue, call
            interface_ddG which returns the "interaction energy"
        b. writing these results to an output file
        c. printing these results

"""

# the Interface object is required by this script
from rosetta.protocols.scoring import Interface
from rosetta import *
from pyrosetta import *
# added by colin for pyrosetta4 compatibility
import pyrosetta.rosetta.protocols as protocols

#########
# Methods

# performs general scanning
#def scanning(pdb_filename, partners, mutant_aa = 'A',
def scanning(pdb_filename, partners, mutant_aa,
        interface_cutoff = 8.0, output = False,
        trials = 1, trial_output = ''):
    """
    Performs "scanning" at an interface within  <pdb_filename>  between
        <partners>  by mutating relevant residues to  <mutant_aa>  and repacking
        residues within  <pack_radius>  Angstroms, further repacking all
        residues within  <interface_cutoff>  of the interface residue, scoring
        the complex and subtracting the score of a pose with the partners
        separated by 500 Angstroms.
        <trials>  scans are performed (to average results) with summaries written
        to  <trial_output>_(trial#).txt.
        Structures are exported to a PyMOL instance.

    """
    # 1. create a pose from the desired PDB file
    pose = Pose()
    pose_from_file(pose, pdb_filename)

    # 2. setup the docking FoldTree and other related parameters
    dock_jump = 1
    movable_jumps = Vector1([dock_jump])
#    protocols.docking.setup_foldtree(pose, partners, movable_jumps)
# Commented out by colin because of error, found that API lists this method as below in PyRosetta4
    pyrosetta.rosetta.protocols.docking.setup_foldtree(pose, partners, movable_jumps)

    # 3. create ScoreFuncions for the Interface and "ddG" calculations
    # the pose's Energies objects MUST be updated for the Interface object to
    #    work normally
    scorefxn = get_fa_scorefxn() #  create_score_function('standard')
    scorefxn(pose)    # needed for proper Interface calculation

    # setup a "ddG" ScoreFunction, custom weights
    ddG_scorefxn = ScoreFunction()
    ddG_scorefxn.set_weight(core.scoring.fa_atr, 0.44)
    ddG_scorefxn.set_weight(core.scoring.fa_rep, 0.07)
    ddG_scorefxn.set_weight(core.scoring.fa_sol, 1.0)
    ddG_scorefxn.set_weight(core.scoring.hbond_bb_sc, 0.5)
    ddG_scorefxn.set_weight(core.scoring.hbond_sc, 1.0)

    # 4. create an Interface object for the pose
    interface = Interface(dock_jump)
    interface.distance(interface_cutoff)
    interface.calculate(pose)

    # 5. create a PyMOLMover for sending output to PyMOL (optional)
    pymover = PyMOLMover()
    pymover.keep_history(True)    # for multiple trajectories
    pymover.apply(pose)
    pymover.send_energy(pose)

    # 6. perform scanning trials
    # the large number of packing operations introduces a lot of variability,
    #    for best results, perform several trials and average the results,
    #    these score changes are useful to QUALITATIVELY defining "hotspot"
    #    residues
    # this script does not use a PyJobDistributor since no PDB files are output
    for trial in range( trials ):
        # store the ddG values in a dictionary
        ddG_mutants = {}
        for i in range(1, pose.total_residue() + 1):
            # for residues at the interface
            if interface.is_interface(i) == True:
                # this way you can TURN OFF output by providing False arguments
                #    (such as '', the default)
                filename = ''
                if output:
                    filename = pose.pdb_info().name()[:-4] + '_' +\
                        pose.sequence()[i-1] +\
                        str(pose.pdb_info().number(i)) + '->' + mutant_aa
                # determine the interace score change upon mutation
                ddG_mutants[i] = interface_ddG(pose, i, mutant_aa,
                    movable_jumps, ddG_scorefxn, interface_cutoff, filename )

        # output results
        print( '='*80 )
        print( 'Trial', str( trial + 1 ) )
        print( 'Mutants (PDB numbered)\t\"ddG\" (interaction dependent score change)' )
        residues = list( ddG_mutants.keys() )  # list(...) conversion is for python3 compatbility
        residues.sort()    # easier to read
        display = [pose.sequence()[i - 1] +
            str(pose.pdb_info().number(i)) + mutant_aa + '\t' +
            str(ddG_mutants[i]) + '\n'
            for i in residues]
        print( ''.join(display)[:-1] )
        print( '='*80 )

        # write to file
        f = open(trial_output + '_' + str(trial + 1) + '.txt' , 'w' )
        f.writelines(display)
        f.close()

    #### alternate output using scanning_analysis (see below), only display
    ####    mutations with "deviant" score changes
    # commented out by colin
#     print( 'Likely Hotspot Residues' )
#     for hotspot in scanning_analysis(trial_output):
#         print( hotspot )
#     print( '='*80 )

"""
1.  creates a copy of the pose
2.  sets up a specific "ddG" ScoreFunction (if no ScoreFunction is provided)
3.  creates a copy of the pose to mutate
4.  mutates a single residue using mutate_residue
5.  calculates the "interaction energy" ( or "binding energy")
6.  outputs structures (optionally):
        -to PyMOL
        -to a PDB file
"""
# returns the "interaction energy" for the pose with a given mutation
def interface_ddG( pose, mutant_position, mutant_aa, movable_jumps, scorefxn = '',
        cutoff = 8.0, out_filename = ''):
    # 1. create a reference copy of the pose
    wt = Pose()    # the "wild-type"
    wt.assign(pose)

    # 2. setup a specific default ScoreFunction
    if not scorefxn:
        # this is a modified version of the scoring function discussed in
        #    PNAS 2002 (22)14116-21, without environment dependent hbonding
        scorefxn = ScoreFunction()
        scorefxn.set_weight(fa_atr, 0.44)
        scorefxn.set_weight(fa_rep, 0.07)
        scorefxn.set_weight(fa_sol, 1.0)
        scorefxn.set_weight(hbond_bb_sc, 0.5)
        scorefxn.set_weight(hbond_sc, 1.0)

    # 3. create a copy of the pose for mutation
    mutant = Pose()
    mutant.assign(pose)

    # 4. mutate the desired residue
    # the pack_radius argument of mutate_residue (see below) is redundant
    #    for this application since the area around the mutation is already
    #    repacked
    mutant = mutate_residue(mutant, mutant_position, mutant_aa,
        0.0, scorefxn)

    # 5. calculate the "interaction energy"
    # the method calc_interaction_energy is exposed in PyRosetta however it
    #    does not alter the protein conformation after translation and may miss
    #    significant interactions
    # an alternate method for manually separating and scoring is provided called
    #    calc_binding_energy (see Interaction Energy vs. Binding Energy below)
    wt_score = calc_binding_energy(wt, scorefxn,
        mutant_position, cutoff)
    mut_score = calc_binding_energy(mutant, scorefxn,
        mutant_position, cutoff)
    #### the method calc_interaction_energy separates an input pose by
    ####    500 Angstroms along the jump defined in a Vector1 of jump numbers
    ####    for movable jumps, a ScoreFunction must also be provided
    #### if setup_foldtree has not been applied, calc_interaction_energy may be
    ####    wrong (since the jumps may be wrong)
    #wt_score = calc_interaction_energy(wt, scorefxn, movable_jumps)
    #mut_score = calc_interaction_energy(mutant, scorefxn, movable_jumps)
    ddg = mut_score - wt_score

    # 6. output data (optional)
    # -export the mutant structure to PyMOL (optional)
    mutant.pdb_info().name( pose.sequence()[mutant_position -1] +
        str( pose.pdb_info().number(mutant_position)) +
        mutant.sequence()[mutant_position - 1])
    pymover = PyMOLMover()
    scorefxn(mutant)
    pymover.apply(mutant)
    pymover.send_energy(mutant)

    # -write the mutant structure to a PDB file
    if out_filename:
        mutant.dump_pdb(out_filename)

    return ddg

# a different version of mutate_residue is provided in PyRosetta v2.0 and
#    earlier that does not optionally repack nearby residues

# replaces the residue at  <resid>  in  <pose>  with  <new_res>  with repacking
def mutate_residue(pose, mutant_position, mutant_aa,
        pack_radius = 0.0, pack_scorefxn = '' ):
    """
    Replaces the residue at  <mutant_position>  in  <pose>  with  <mutant_aa>
        and repack any residues within  <pack_radius>  Angstroms of the mutating
        residue's center (nbr_atom) using  <pack_scorefxn>
    note: <mutant_aa>  is the single letter name for the desired ResidueType

    example:
        mutate_residue(pose, 30, A)
    See also:
        Pose
        PackRotamersMover
        MutateResidue
        pose_from_sequence
    """
    #### a MutateResidue Mover exists similar to this except it does not pack
    ####    the area around the mutant residue (no pack_radius feature)
    #mutator = MutateResidue(mutant_position, mutant_aa)
    #mutator.apply(test_pose)

    if pose.is_fullatom() == False:
        IOError( 'mutate_residue only works with fullatom poses' )

    test_pose = Pose()
    test_pose.assign(pose)

    # create a standard scorefxn by default
    if not pack_scorefxn:
        pack_scorefxn = get_fa_scorefxn() #  create_score_function('standard')

    task = standard_packer_task(test_pose)

    # the Vector1 of booleans (a specific object) is needed for specifying the
    #    mutation, this demonstrates another more direct method of setting
    #    PackerTask options for design
    aa_bool = rosetta.utility.vector1_bool()
    # PyRosetta uses several ways of tracking amino acids (ResidueTypes)
    # the numbers 1-20 correspond individually to the 20 proteogenic amino acids
    # aa_from_oneletter returns the integer representation of an amino acid
    #    from its one letter code
    # convert mutant_aa to its integer representation
    mutant_aa = core.chemical.aa_from_oneletter_code(mutant_aa)

    # mutation is performed by using a PackerTask with only the mutant
    #    amino acid available during design
    # to do this, construct a Vector1 of booleans indicating which amino acid
    #    (by its numerical designation, see above) to allow
    for i in range(1, 21):
        # in Python, logical expression are evaluated with priority, thus the
        #    line below appends to aa_bool the truth (True or False) of the
        #    statement i == mutant_aa
        aa_bool.append( i == int(mutant_aa) )

    # modify the mutating residue's assignment in the PackerTask using the
    #    Vector1 of booleans across the proteogenic amino acids
    task.nonconst_residue_task(mutant_position
        ).restrict_absent_canonical_aas(aa_bool)

    # prevent residues from packing by setting the per-residue "options" of
    #    the PackerTask
    center = pose.residue(mutant_position).nbr_atom_xyz()
    for i in range(1, pose.total_residue() + 1):
        # only pack the mutating residue and any within the pack_radius
        if not i == mutant_position or center.distance_squared(
                test_pose.residue(i).nbr_atom_xyz()) > pack_radius**2:
            task.nonconst_residue_task(i).prevent_repacking()

    # apply the mutation and pack nearby residues
    # changed by colin for rpy4 compat
    packer = protocols.minimization_packing.PackRotamersMover(pack_scorefxn, task)
    packer.apply(test_pose)

    return test_pose

# there is a significant difference between interaction energy and binding
#    energy (see Interaction Energy vs. Binding Energy below)
def calc_binding_energy(pose, scorefxn, center, cutoff = 8.0):
    # create a copy of the pose for manipulation
    test_pose = Pose()
    test_pose.assign(pose)

    # setup packer options
    # the sidechain conformations of residues "near the interface", defined as
    #    within  <cutoff>  Angstroms of an interface residue, may change and
    #    must be repacked, if all residues are repacked, aberrant sidechain
    #    conformations near the interface, but independent of complex
    #    interactions, will be repacked for the mutant and wild-type structures
    #    preventing them from adding noise to the score difference
    # this method of setting up a PackerTask is different from packer_task.py
    tf = standard_task_factory()    # create a TaskFactory
    tf.push_back(core.pack.task.operation.RestrictToRepacking())    # restrict it to repacking

    # this object contains repacking options, instead of turning the residues
    #    "On" or "Off" directly, this will create an object for these options
    #    and assign it to the TaskFactory
    prevent_repacking = core.pack.task.operation.PreventRepacking()

    # the "center" (nbr_atom) of the mutant residue, for distance calculation
    center = test_pose.residue(center).nbr_atom_xyz()
    for i in range(1, test_pose.total_residue() + 1):
        # the .distance_squared method is (a little) lighter than .norm
        # if the residue is further than <cutoff> Angstroms away, do not repack
        if center.distance_squared(
                test_pose.residue(i).nbr_atom_xyz()) > cutoff**2:
            prevent_repacking.include_residue(i)

    # apply these settings to the TaskFactory
    tf.push_back(prevent_repacking)

    # setup a PackRotamersMover
    # changed by colin
    packer = protocols.minimization_packing.PackRotamersMover(scorefxn)
    packer.task_factory(tf)

    #### create a Mover for performing translation
    #### RigidBodyTransMover is SUPPOSED to translate docking partners of a
    ####    pose based on an axis and magnitude
    #### test it using the PyMOLMover, it does not perform a simple translation
    ####    I also observed a "Hbond Tripped" error when packing after applying
    ####    the Mover, it appears to store inf and NaN values into hbonds
    #transmover = RigidBodyTransMover()
    # calc_interaction_energy separates the chains by 500.0 Angstroms,
    #    so does this Mover
    # if using this Mover, the step_size MUST be a float
    # if this setting is left to default, it will move the proteins
    #    VERY far apart
    #transmover.step_size( 5.0 )

    # repack the test_pose
    packer.apply(test_pose)

    # score this structure
    before = scorefxn(test_pose)

    # separate the docking partners
    #### since RigidBodyTransMover DOES NOT WORK, it is not used
    #transmover.apply(test_pose)

    # here are two methods for applying a translation onto a pose structure
    # both require an xyzVector
    xyz = rosetta.numeric.xyzVector_double_t()    # a Vector for coordinates
    xyz.x = 500.0    # arbitrary separation magnitude, in the x direction
    xyz.y = 0.0    #...I didn't have this and it defaulted to 1e251...?
    xyz.z = 0.0    #...btw thats like 1e225 light years,
                   #    over 5e245 yrs at Warp Factor 9.999 (thanks M. Pacella)

    #### here is a hacky method for translating the downstream partner of a
    #    pose protein-protein complex (must by two-body!)
    chain2starts = len(pose.chain_sequence(1)) + 1
    for r in range(chain2starts, test_pose.total_residue() + 1):
        for a in range(1, test_pose.residue(r).natoms() + 1):
            test_pose.residue(r).set_xyz(a,
                test_pose.residue(r).xyz(a) + xyz)

    # here is an elegant way to do it, it assumes that jump number 1
    #    defines the docking partners "connectivity"
    # the pose.jump method returns a jump object CREATED from the pose jump
    #    data, the pose itself does not own a Jump object, thus you can use
    #    Jump methods, such as pose.jump(1).set_translation, however the object
    #    has not been properly constructed for manipulation, thus performing
    #    a change does not cause any problems, but is not permanently applied
    #translate = test_pose.jump( 1 )    # copy this information explicitly
    # adjust its translation via vector addition
    #translate.set_translation( translate.get_translation() + xyz )
    #test_pose.set_jump( 1 , translate )
    # as explained above, this call will NOT work
    #test_pose.jump(1).set_translation( test_pose.get_translation() + xyz )

    # repack the test_pose after separation
    packer.apply(test_pose)

    # return the change in score
    return before - scorefxn(test_pose)


# this is a peripheral method for performing analysis on the output files
# it is not used by default but demonstrates easy data manipulation in Python
# this method averages the output from all "ddG" data files and returns the
#    mutations which are more than 1 standard deviation away from the mean
def scanning_analysis(trial_output):
    """
    Average the values of all files in this directory with  <trial_output>  in
        their title and return the mutations (rows) that are 1 or more standard
        deviations from the mean score change

    """
    # extract all files
    filenames = os.listdir(os.getcwd())
    # remove files that don't have trial_output in their name, this assumes
    #    these are the only relevant files, otherwise this will FAIL!
    filenames =[i for i in filenames if trial_output in i]

    # perform an initial reading, to setup lists
    filename = filenames[0]
    f = open(filename , 'r')
    data = f.readlines()
    data = [i.strip() for i in data]    # remove "\n"
    f.close()

    # list of mutations, should be identical for all output files
    mutants = [i.split('\t')[0] for i in data]
    ddg = [float(i.split('\t')[1]) for i in data]

    # for all files beyond the first, add the "ddG" values
    for filename in filenames[1:]:
        f = open( filename , 'r' )
        data = f.readlines()
        data = [i.strip() for i in data]
        f.close()

        ddg = [float(data[i].split('\t')[1])+ddg[i] for i in range(len(data))]

    # average by dividing by the number of files
    ddg = [i/len(filenames) for i in ddg]

    # take the mean
    mean = sum(ddg)/len(ddg)
    # determine the second central moment
    std = [(i-mean)**2 for i in ddg]
    std = (sum(std)/len(std))**.5

    # extract list elements (for ddg and thus mutants) with a ddg value more
    #    than 1 standard deviation away
    significant = [i for i in range(len(ddg)) if abs(ddg[i]-mean)>std]
    # these are the hotspots
    hotspots = [mutants[i] for i in significant]

    return hotspots

################################################################################
# INTERPRETING RESULTS

"""
The output file(s) for this script are tab delimited columns of mutants
(designated by the single letter amino acid representation of the original
sequence,  the PDB number, and the single letter amino acid representation of
the new residue) and the change in score. The Rosetta score functions are not
scaled to any physical value and proteins vary greatly so the output score
changes cannot easily be interpreted.

The optional method 




nysis averages the values in these files and
outputs mutations with potentially significant interactions. Packing makes this
algorithm VERY NOISY requiring several trials for results to converge. Using the
default "-constant_seed", the script itself is deterministic for convenience.

Residues which change score significantly are likely to contribute significant
interactions which stabilize the protein-protein complex. Since only residues
near the protein-protein interface are considered, the score changes that are
statistically significant indicate potential energetic effects. Small score
changes are most likely noise resulting from repacking unimportant residues
near the protein-protein interface.

Since Rosetta scores do not scale with any physical units, the sign of the
change should be interpreted qualitatively. Positive changes in score indicate
poorer binding upon mutation. Negative changes in score indicate better binding
with the new mutant (default alanine). For more accurate results, performs
several trials and average the individual residue changes in score.

"""

#######################################
# Interaction Energy vs. Binding Energy
"""
The analysis performed by this script is hampered by the fact that there is no
standard method for converting a PDB into its solution-state structure.
Simplistically, a protein-protein interaction can be modeled as:

A <--> A* <--\
              \
               --> A*B*
              /
B <--> B* <--/

Interaction Energy:    A* + B* <--> A*B*
Binding Energy:        A  + B  <--> A*B*

Where protein A changes to state A* and protein B changes to state B* followed
by the formation of complex A*B*. A and B represent the solution-state
conformations of proteins A and B respectively. A* and B* represent the bound
conformations of proteins A and B respectively. In this case, the interaction
energy between proteins A and B is the change in energy for the process of A*
and B* forming a complex (contextual energy changes due to the presence of the
other partner). The binding energy is the interaction energy plus the energy
involved in the conversion of A to A* and B to B*.

Rosetta score is analogous to energy in many ways but it not explicit physical
energy. As such, neither physical interaction energy or physical binding energy
is calculable with accuracy using Rosetta. Without a protocol for converting a
structure to its solution state, the binding energy is not directly accessible
(i.e. some dependence on sampling). The method calc_interaction_energy truly
calculates the change in score due to inter-protein interactions. The custom
method calc_binding_energy (provided in this script) assumes that simple
repacking of the entire protein is sufficient to convert an unbound protein
from its bound conformation to it solution-state conformation.

"""

################################################################################
# COMMANDLINE COMPATIBILITY

# everything below is added to provide commandline usage,
#   the available options are specified below
# this method:
#    1. defines the available options
#    2. loads in the commandline or default values
#    3. calls scanning with these values

# parser object for managing input options
# all defaults are for the example using "test_dock.pdb" with one trial
#    to provide results quickly
# commented out by colin
# parser = optparse.OptionParser()
# parser.add_option('--pdb_filename', dest = 'pdb_filename',
#     default = '../test/data/test_dock.pdb',    # default example PDB
#     help = 'the PDB file containing the protein to refine')
# # for more information on "partners", see sample_docking step 2.
# parser.add_option('--partners', dest = 'partners',
#     default = 'E_I',    # default for the example test_dock.pdb
#     help = 'the relative chain partners for docking')
# # scanning options
# parser.add_option('--mutant_aa', dest = 'mutant_aa',
#     default = 'A',    # default to alanine, A
#     help = 'the amino acid to mutate all residues to')
# parser.add_option('--interface_cutoff', dest = 'interface_cutoff',
#     default = '8.0',    # default to 8.0 Angstroms
#     help = 'the distance (in Angstroms) to detect residues for repacking\
#         near the interface')
# parser.add_option('--output', dest = 'output',
#     default = '',    # default off, do now write to file
#     help = 'if True, mutant structures are written to PDB files')
# # trials options
# parser.add_option('--trials', dest='trials',
#     default = '1',    # default to single trial for speed
#     help = 'the number of trials to perform')
# parser.add_option('--trial_output', dest = 'trial_output',
#     default = 'ddG_out',    # if a specific output name is desired
#     help = 'the name preceding all output files')
# (options,args) = parser.parse_args()

# # PDB file option
# pdb_filename = options.pdb_filename
# partners = options.partners
# # scanning options
# mutant_aa = options.mutant_aa
# interface_cutoff = float(options.interface_cutoff)
# output = bool(options.output)
# # trials options
# trials = int(options.trials)
# trial_output = options.trial_output

# scanning(pdb_filename, partners, mutant_aa,
#     interface_cutoff, output, trials, trial_output)

################################################################################
# ALTERNATE SCENARIOS

################
# A Real Example
"""
All of the default variables and parameters used above are specific to
the example with "test_dock.pdb", which is supposed to be simple,
straightforward, and speedy. Here is a more practical example:

The influenza protein NS1 is implicated to increase virulence. Suppose you are
curious about the molecular mechanism of binding for this protein and decide
to investigate using PyRosetta.

1. Download a copy of RCSB PDB file 3RT3 (remove waters and any other HETATM)
2. Make a directory containing:
        -the PDB file for 3RT3 (cleaned of HETATMs and waters)
            lets name it "3RT3.clean.pdb" here
        -this sample script (technically not required, but otherwise the
            commands in 3. would change since docking.py wouldn't be here)
3. Run the script from the commandline with appropriate arguments:

>python ala_scan.py --pdb_filename=3RT3.clean.pdb --partners=B_C --mutant_aa=A --interface_cutoff=8.0 --trials=20 --trial_output=3RT3_ddG --PyMOLMover_ip=off

        -The partners option, "B_C" is PDB specific, if you change the chain
            IDs in 3RT3, make sure this matches
        -for alanine scanning, all residues must be mutated to alanine (A)
        -an interface_cutoff length of 8.0 Angstroms is sufficient to include
            all potential interface residues (there is currently to standard way
            to identify interface residues, however 8 Angstroms is large enough
            to account for even the largest protein-protein interfaces)
        -the "--output" option is unused to prevent unwanted mutant structures
            from being written to file
        -20 trajectories should be sufficient to "average-out" noise due to
            the stochasticity of packing

4. Wait for output, this will take a little while
5. Analyze the results (see INTERPRETING RESULTS above)

Note: this is NOT intended to be used for realistic , alanine scanning
it merely provides a "skeleton" for the code in PyRosetta. It may be useful
for preliminary investigation but the best protocols are somewhat
protein-specific, there is no current universal  method. Generally,
a protocol similar to the one presented here with more drastic sampling and
a larger number of trials should be sufficient to find

"""

##############################
# Changing Scanning Sampling
"""
As dicussed above and in previous scripts (such as refinement.py), there is no
standard method for converting a protein structure into its solution-state
structure. Rosetta refinement is a very good protocol for predicting these
conformation since it accepts moves based on physical constraints and
statistical relevance (the Rosetta scores are effectively "PDB-likeness"
scores). Without a trusted solution state structure, the "binding energy" is
elusive.

Sampling in this script ASSUMES:
    -repacking effectively predicts the conformational changes due to mutation
    -repacking an interface will refine (and not disrupt) interactions
    -repacking bound conformation (while unbound) predicts the solution-state
        structure

This method will ABSOLUTELY miss any mutations which significantly effect the
kinetics of folding. Currently, no kinetic data can be withdrawn from Rosetta
simulations. The mutation method above is analogous to the physical process of
instantaneously mutating an amino acid and disregards any disruption of the
protein fold based on kinetic inaccessibility (a priori, residue identity may
have evolved to produce the proper folding pathway and these mutations start
from this fold). However, local disruptions in score upon mutation often
indicate poor mutations and full ab initio predictions are wasteful.

The accuracy of this script depends directly on the sampling techniques used to
determine the impact of sequence changes on structure and the solution-state
structure of a protein. MANY alternate methods could potentially increase the
accuracy of this script. Although alanine is preferred for obvious experimental
reasons, this script can perform scanning with any desired proteogenic amino
acid.

Please try alternate sampling methods to better understand how these
algorithms perform and to find what moves best suite your problem.

Note: there is a "ddGMover" exposed in PyRosetta however it is untested,
this Mover likely applies a similar protocol to that above

"""

#############################
# Changing Scanning Scoring
"""
The "ddG ScoreFunction" used here is used in other similar Rosetta applications
(Rosetta actually contains a more refined alanine scanning protocol, "ddG").
Like ligand interaction scoring, scanning is more accurate if the score terms
which represent enthalpic bonuses (i.e. hydrogen bond formation, proper charge
interactions, etc.) have higher weights. Since Rosetta scores are not
energetically accurate, it is better to aim for qualitative predictions (i.e.
hydrogen bonding at the interface, hydrophic interactions, etc.). Alanine
scanning is a simple adaptation of the Rosetta code structure to different
biochemical problem and the currently used scoring function has not been
optimized for predictive accuracy. Many score terms and weight sets are likely
to elucidate important protein-protein interface interactions.

Please try alternate scoring functions or unique selection methods to better
understand which scoring terms contribute to performance and to find what
scoring best suites your problem.

"""
