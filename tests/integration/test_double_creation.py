import time
import pytest
import rethinkdb as r

from bigchaindb import Bigchain


@pytest.fixture
def inputs(user_vk):
    from bigchaindb.models import Transaction

    b = Bigchain()

    # create blocks with transactions for `USER` to spend
    for block in range(4):
        transactions = [
            Transaction.create(
                [b.me], [user_vk], metadata={'i': i}).sign([b.me_private])
            for i in range(10)
        ]
        block = b.create_block(transactions)
        b.write_block(block, durability='hard')


@pytest.mark.usefixtures('processes')
def test_fast_double_create(b, user_vk):
    from bigchaindb.models import Transaction
    tx = Transaction.create([b.me], [user_vk],
                            metadata={'test': 'test'}).sign([b.me_private])

    # write everything fast
    b.write_transaction(tx)
    b.write_transaction(tx)

    time.sleep(2)
    tx_returned = b.get_transaction(tx.id)

    # test that the tx can be queried
    assert tx_returned == tx
    # test the transaction appears only once
    assert len(list(r.table('bigchain')
                    .get_all(tx.id, index='transaction_id')
                    .run(b.conn))) == 1


@pytest.mark.usefixtures('processes')
def test_double_create(b, user_vk):
    from bigchaindb.models import Transaction
    tx = Transaction.create([b.me], [user_vk],
                            metadata={'test': 'test'}).sign([b.me_private])

    b.write_transaction(tx)
    time.sleep(2)
    b.write_transaction(tx)
    time.sleep(2)
    tx_returned = b.get_transaction(tx.id)

    # test that the tx can be queried
    assert tx_returned == tx
    # test the transaction appears only once
    assert len(list(r.table('bigchain')
                    .get_all(tx.id, index='transaction_id')
                    .run(b.conn))) == 1


@pytest.mark.usefixtures('processes', 'inputs')
def test_get_owned_ids_works_after_double_spend(b, user_vk, user_sk):
    """See issue 633."""
    from bigchaindb.models import Transaction
    input_valid = b.get_owned_ids(user_vk).pop()
    input_valid = b.get_transaction(input_valid.txid)
    tx_valid = Transaction.transfer(input_valid.to_inputs(),
                                    [user_vk],
                                    input_valid.asset).sign([user_sk])

    # write the valid tx and wait for voting/block to catch up
    b.write_transaction(tx_valid)
    time.sleep(2)

    # doesn't throw an exception
    b.get_owned_ids(user_vk)

    # create another transaction with the same input
    tx_double_spend = Transaction.transfer(input_valid.to_inputs(),
                                           [user_vk],
                                           input_valid.asset) \
                                           .sign([user_sk])

    # write the double spend tx
    b.write_transaction(tx_double_spend)
    time.sleep(2)

    # still doesn't throw an exception
    b.get_owned_ids(user_vk)

    assert b.is_valid_transaction(tx_double_spend) is False
