# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import json  # noqa: F401
import time
import shutil

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint  # noqa: F401

from biokbase.workspace.client import Workspace as workspaceService
from jgi_mg_assembly.jgi_mg_assemblyImpl import jgi_mg_assembly
from jgi_mg_assembly.jgi_mg_assemblyServer import MethodContext
from jgi_mg_assembly.authclient import KBaseAuth as _KBaseAuth

from AssemblyUtil.AssemblyUtilClient import AssemblyUtil
from ReadsUtils.ReadsUtilsClient import ReadsUtils


class jgi_mg_assemblyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('jgi_mg_assembly'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'jgi_mg_assembly',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL)
        cls.serviceImpl = jgi_mg_assembly(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_jgi_mg_assembly_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa
    def load_fasta_file(self, filename, obj_name, contents):
        f = open(filename, 'w')
        f.write(contents)
        f.close()
        assemblyUtil = AssemblyUtil(self.callback_url)
        assembly_ref = assemblyUtil.save_assembly_from_fasta({'file': {'path': filename},
                                                              'workspace_name': self.getWsName(),
                                                              'assembly_name': obj_name
                                                              })
        return assembly_ref

    def load_pe_reads(self, fwd_file, rev_file):
        """
        Copies from given dir to scratch. Then calls ReadsUtils to upload from scratch.
        """
        fwd_file_path = os.path.join(self.scratch, "fwd_file.fastq")
        rev_file_path = os.path.join(self.scratch, "rev_file.fastq")
        shutil.copy(fwd_file, fwd_file_path)
        shutil.copy(rev_file, rev_file_path)
        ru = ReadsUtils(self.callback_url)
        pe_reads_params = {
            'fwd_file': fwd_file_path,
            'rev_file': rev_file_path,
            'sequencing_tech': 'Illumina',
            'wsname': self.getWsName(),
            'name': 'MyPairedEndLibrary'
        }
        return ru.upload_reads(pe_reads_params)['obj_ref']

    def test_run_pipeline_ok(self):
        # load some data here.
        reads_upa = self.load_pe_reads(os.path.join("data", "small.forward.fq"), os.path.join("data", "small.reverse.fq"))
        output = self.getImpl().run_mg_assembly_pipeline(self.getContext(), {
            "reads_upa": reads_upa,
            "output_assembly_name": "MyNewAssembly",
            "workspace_name": self.getWsName()
        })[0]

        self.assertIn('report_name', output)
        self.assertIn('report_ref', output)
        self.assertIn('assembly_upa', output)
        pprint(output)

    # # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa
    # def test_filter_contigs_ok(self):
    #
    #     # First load a test FASTA file as an KBase Assembly
    #     fasta_content = '>seq1 something soemthing asdf\n' \
    #                     'agcttttcat\n' \
    #                     '>seq2\n' \
    #                     'agctt\n' \
    #                     '>seq3\n' \
    #                     'agcttttcatgg'
    #
    #     assembly_ref = self.load_fasta_file(os.path.join(self.scratch, 'test1.fasta'),
    #                                         'TestAssembly',
    #                                         fasta_content)
    #
    #     # Second, call your implementation
    #     ret = self.getImpl().filter_contigs(self.getContext(),
    #                                         {'workspace_name': self.getWsName(),
    #                                          'assembly_input_ref': assembly_ref,
    #                                          'min_length': 10
    #                                          })
    #
    #     # Validate the returned data
    #     self.assertEqual(ret[0]['n_initial_contigs'], 3)
    #     self.assertEqual(ret[0]['n_contigs_removed'], 1)
    #     self.assertEqual(ret[0]['n_contigs_remaining'], 2)
    #
    # def test_filter_contigs_err1(self):
    #     with self.assertRaises(ValueError) as errorContext:
    #         self.getImpl().filter_contigs(self.getContext(),
    #                                       {'workspace_name': self.getWsName(),
    #                                        'assembly_input_ref': '1/fake/3',
    #                                        'min_length': '-10'})
    #     self.assertIn('min_length parameter cannot be negative', str(errorContext.exception))
    #
    # def test_filter_contigs_err2(self):
    #     with self.assertRaises(ValueError) as errorContext:
    #         self.getImpl().filter_contigs(self.getContext(),
    #                                       {'workspace_name': self.getWsName(),
    #                                        'assembly_input_ref': '1/fake/3',
    #                                        'min_length': 'ten'})
    #     self.assertIn('Cannot parse integer from min_length parameter', str(errorContext.exception))
